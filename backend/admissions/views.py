import re
import uuid
import csv
import io
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.http import FileResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from .auth_services import issue_otp_pair, verify_otp_pair
from .models import Application, AuditLog, OTPChallenge, PasswordResetIntent, RegistrationIntent, ShareholderClaim, StudentDocument, StudentRecord, VerificationRun
from .permissions import IsStaffUser
from .serializers import FeeEstimateInputSerializer, LoginSerializer, PasswordResetCompleteSerializer, PasswordResetStartSerializer, RegistrationStartSerializer, RegistrationVerifySerializer, ShareholderClaimSerializer, StaffStudentDocumentUploadSerializer, StaffStudentRecordSerializer, StudentApplicationSerializer, StudentDocumentUploadSerializer
from .services import calculate_latest_fee


def normalize_mobile(value):
    digits = re.sub(r"\D", "", value)
    return digits[2:] if digits.startswith("91") and len(digits) == 12 else digits


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        account = get_user_model().objects.filter(username__iexact=values["username"].strip()).first()
        user = authenticate(request, username=account.get_username() if account else values["username"], password=values["password"])
        if user is None:
            return Response({"detail": "The username or password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response({"username": user.get_username(), "is_staff": user.is_staff, "detail": "Signed in."})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"detail": "Signed out."})


class RegistrationStartView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegistrationStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        prn = values["prn"].strip().upper()
        email = values["email"].strip().lower()
        mobile = normalize_mobile(values["mobile"])
        name = " ".join(values["full_name"].split())
        record = StudentRecord.objects.filter(prn=prn, email__iexact=email, mobile=mobile, user__isnull=True).first()
        if not record or " ".join(record.full_name.split()).casefold() != name.casefold():
            raise ValidationError({"detail": "We could not match these details to a student record uploaded by college staff. Check the PRN and contact the admissions office."})
        if get_user_model().objects.filter(username__iexact=prn).exists():
            raise ValidationError({"detail": "An account already exists for this PRN. Try signing in or resetting your password."})
        try:
            validate_password(values["password"])
        except DjangoValidationError as exc:
            raise ValidationError({"password": list(exc.messages)}) from exc
        challenge_id = uuid.uuid4()
        with transaction.atomic():
            intent = RegistrationIntent.objects.create(challenge_id=challenge_id, prn=prn, full_name=name, email=email, mobile=mobile,
                entry_year=values["entry_year"], password_hash=make_password(values["password"]), expires_at=timezone.now() + timedelta(minutes=10))
            issue_otp_pair(challenge_id=challenge_id, email=email, mobile=mobile, purpose=OTPChallenge.Purpose.REGISTER)
        return Response({"challenge_id": str(intent.challenge_id), "delivery_mode": "development-console" if settings.DEBUG else "configured-providers", "detail": "Verification codes sent to the registered email and mobile. They expire in five minutes."}, status=status.HTTP_201_CREATED)


class RegistrationVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegistrationVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        with transaction.atomic():
            try:
                intent = RegistrationIntent.objects.select_for_update().get(challenge_id=values["challenge_id"], consumed_at__isnull=True)
            except RegistrationIntent.DoesNotExist as exc:
                raise NotFound("Registration request is invalid or expired. Start registration again.") from exc
            if intent.expires_at <= timezone.now():
                raise ValidationError({"detail": "Registration code expired. Start registration again."})
            valid = verify_otp_pair(challenge_id=intent.challenge_id, purpose=OTPChallenge.Purpose.REGISTER, email_code=values["email_code"], mobile_code=values["mobile_code"])
            if not valid:
                return Response({"detail": "One or both codes are incorrect, expired, or already used."}, status=status.HTTP_400_BAD_REQUEST)
            record = StudentRecord.objects.select_for_update().filter(prn=intent.prn, email__iexact=intent.email, mobile=intent.mobile, user__isnull=True).first()
            if not record:
                raise ValidationError({"detail": "The student record is no longer available for account creation. Contact staff."})
            User = get_user_model()
            if User.objects.filter(username__iexact=intent.prn).exists():
                raise ValidationError({"detail": "An account already exists for this PRN."})
            user = User(username=intent.prn, email=intent.email, password=intent.password_hash)
            user.save()
            record.user = user
            record.save(update_fields=["user", "updated_at"])
            intent.consumed_at = timezone.now()
            intent.save(update_fields=["consumed_at"])
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"username": user.get_username(), "is_staff": False, "detail": "Account verified and created."}, status=status.HTTP_201_CREATED)


class PasswordResetStartView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"].strip()
        mobile = normalize_mobile(identifier)
        from django.db.models import Q
        record = StudentRecord.objects.select_related("user").filter(Q(prn__iexact=identifier) | Q(email__iexact=identifier) | Q(mobile=mobile)).first()
        challenge_id = uuid.uuid4()
        if record and record.user_id:
            with transaction.atomic():
                PasswordResetIntent.objects.create(challenge_id=challenge_id, user=record.user, expires_at=timezone.now() + timedelta(minutes=10))
                issue_otp_pair(challenge_id=challenge_id, email=record.email, mobile=record.mobile, purpose=OTPChallenge.Purpose.PASSWORD_RESET)
        # Same response for known and unknown identifiers to reduce account enumeration.
        return Response({"challenge_id": str(challenge_id), "delivery_mode": "development-console" if settings.DEBUG else "configured-providers", "detail": "If the account is eligible, verification codes have been sent to its registered email and mobile."})


class PasswordResetCompleteView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        with transaction.atomic():
            try:
                intent = PasswordResetIntent.objects.select_for_update().select_related("user").get(challenge_id=values["challenge_id"], consumed_at__isnull=True)
            except PasswordResetIntent.DoesNotExist as exc:
                raise NotFound("Reset request is invalid or expired. Start password recovery again.") from exc
            if intent.expires_at <= timezone.now():
                raise ValidationError({"detail": "Reset codes expired. Start password recovery again."})
            valid = verify_otp_pair(challenge_id=intent.challenge_id, purpose=OTPChallenge.Purpose.PASSWORD_RESET, email_code=values["email_code"], mobile_code=values["mobile_code"])
            if not valid:
                return Response({"detail": "One or both codes are incorrect, expired, or already used."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                validate_password(values["new_password"], user=intent.user)
            except DjangoValidationError as exc:
                raise ValidationError({"new_password": list(exc.messages)}) from exc
            intent.user.set_password(values["new_password"])
            intent.user.save(update_fields=["password"])
            intent.consumed_at = timezone.now()
            intent.save(update_fields=["consumed_at"])
        return Response({"detail": "Password reset successfully. Sign in with your new password."})

@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health(request):
    return Response({"ok": True, "service": "svpm-admissions-api"})

@ensure_csrf_cookie
def csrf_cookie(request):
    return JsonResponse({"detail": "CSRF cookie set"})

class CurrentUserView(APIView):
    def get(self, request):
        return Response({"username": request.user.get_username(), "is_staff": request.user.is_staff})

class StaffPRNLookupView(APIView):
    permission_classes = [IsStaffUser]
    def get(self, request):
        prn = request.query_params.get("prn", "").strip().upper()
        if not prn:
            raise ValidationError({"prn": "PRN is required."})
        try:
            student = StudentRecord.objects.get(prn=prn)
        except ObjectDoesNotExist:
            return Response({"detail": "No student record found for this PRN."}, status=status.HTTP_404_NOT_FOUND)
        AuditLog.objects.create(actor=request.user, action="staff.prn_lookup", target_type="StudentRecord", target_id=str(student.pk), details={"prn": student.prn})
        summary = {"prn": student.prn, "full_name": student.full_name, "email": student.email, "mobile": student.mobile, "aadhaar": f"XXXX-XXXX-{student.aadhaar_last4}" if student.aadhaar_last4 else None, "department": student.department, "year_level": student.year_level, "first_year_admission": student.first_year_admission}
        apps = list(Application.objects.filter(student=student).values("id", "academic_year", "entry_year", "department", "category", "status"))
        return Response({"student": summary, "applications": apps})


class StaffStudentRecordListCreateView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        queryset = StudentRecord.objects.all()
        year_level = request.query_params.get("year_level", "").upper()
        department = request.query_params.get("department", "").strip()
        search = request.query_params.get("search", "").strip()
        if year_level in StudentRecord.YearLevel.values:
            queryset = queryset.filter(year_level=year_level)
        if department:
            queryset = queryset.filter(department__iexact=department)
        if search:
            from django.db.models import Q
            queryset = queryset.filter(Q(prn__icontains=search) | Q(full_name__icontains=search) |
                                       Q(email__icontains=search) | Q(mobile__icontains=search))
        paginator = LimitOffsetPagination()
        paginator.default_limit = 50
        paginator.max_limit = 200
        page = paginator.paginate_queryset(queryset.order_by("department", "full_name"), request, view=self)
        return paginator.get_paginated_response(StaffStudentRecordSerializer(page, many=True).data)

    def post(self, request):
        serializer = StaffStudentRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record = serializer.save()
        except IntegrityError as exc:
            raise ValidationError({"detail": "PRN, email, or mobile is already assigned to another student."}) from exc
        AuditLog.objects.create(actor=request.user, action="staff.student_record.created", target_type="StudentRecord",
                                target_id=str(record.pk), details={"prn": record.prn, "year_level": record.year_level, "department": record.department})
        return Response(StaffStudentRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class StaffStudentRecordDetailView(APIView):
    permission_classes = [IsStaffUser]

    def get_object(self, pk):
        try:
            return StudentRecord.objects.get(pk=pk)
        except StudentRecord.DoesNotExist as exc:
            raise NotFound("Student record not found.") from exc

    def get(self, request, pk):
        return Response(StaffStudentRecordSerializer(self.get_object(pk)).data)

    def patch(self, request, pk):
        record = self.get_object(pk)
        serializer = StaffStudentRecordSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            record = serializer.save()
        except IntegrityError as exc:
            raise ValidationError({"detail": "PRN, email, or mobile is already assigned to another student."}) from exc
        AuditLog.objects.create(actor=request.user, action="staff.student_record.updated", target_type="StudentRecord",
                                target_id=str(record.pk), details={"prn": record.prn, "year_level": record.year_level, "department": record.department})
        return Response(StaffStudentRecordSerializer(record).data)


class StaffStudentRecordImportView(APIView):
    permission_classes = [IsStaffUser]
    required_columns = {"prn", "full_name", "email", "mobile", "department", "year_level"}

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload or not upload.name.lower().endswith(".csv"):
            raise ValidationError({"file": "Choose a CSV file."})
        if upload.size > 3 * 1024 * 1024:
            raise ValidationError({"file": "CSV must be 3 MB or smaller."})
        try:
            text = upload.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames:
                raise ValueError("The CSV has no header row.")
            reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
            missing = self.required_columns - set(reader.fieldnames)
            if missing:
                raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
            rows = list(reader)
        except (UnicodeDecodeError, csv.Error, ValueError) as exc:
            raise ValidationError({"file": str(exc)}) from exc
        if len(rows) > 5000:
            raise ValidationError({"file": "Import up to 5,000 student rows at a time."})

        created = updated = 0
        errors = []
        for row_number, raw in enumerate(rows, start=2):
            values = {str(key).strip().lower(): (value or "").strip() for key, value in raw.items() if key}
            prn = values.get("prn", "").upper()
            record = StudentRecord.objects.filter(prn=prn).first() if prn else None
            serializer = StaffStudentRecordSerializer(record, data=values, partial=record is not None)
            if not serializer.is_valid():
                errors.append({"row": row_number, "prn": prn, "errors": serializer.errors})
                continue
            try:
                with transaction.atomic():
                    saved = serializer.save()
                if record:
                    updated += 1
                else:
                    created += 1
            except IntegrityError:
                errors.append({"row": row_number, "prn": prn, "errors": {"detail": "PRN, email, or mobile conflicts with another record."}})
                continue
            AuditLog.objects.create(actor=request.user, action="staff.student_record.imported", target_type="StudentRecord",
                                    target_id=str(saved.pk), details={"prn": saved.prn, "year_level": saved.year_level, "department": saved.department})
        return Response({"created": created, "updated": updated, "failed": len(errors), "errors": errors})

class FeeEstimateView(APIView):
    def post(self, request):
        incoming = FeeEstimateInputSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = incoming.validated_data
        data = calculate_latest_fee(values["category"], values["gender"], values["has_ebc_ews_certificate"], values["carried_balance"])
        return Response(data)


class StudentDocumentsView(APIView):
    """Student-owned document upload and status endpoint."""

    def get(self, request):
        try:
            student = request.user.student_record
        except ObjectDoesNotExist:
            return Response({"detail": "No staff-uploaded student record is linked to this account."}, status=404)
        documents = StudentDocument.objects.filter(student=student).order_by("-uploaded_at")
        return Response(StudentDocumentUploadSerializer(documents, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = StudentDocumentUploadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        from .ocr_services import verify_document
        run = verify_document(document)
        if run:
            AuditLog.objects.create(actor=request.user, action="document.ocr_completed", target_type="StudentDocument",
                                    target_id=str(document.pk), details={"decision": run.decision, "score": str(run.score)})
        else:
            AuditLog.objects.create(actor=request.user, action="document.uploaded", target_type="StudentDocument",
                                    target_id=str(document.pk), details={"ocr_status": document.ocr_status})
        return Response(StudentDocumentUploadSerializer(document, context={"request": request}).data, status=status.HTTP_201_CREATED)


class StaffStudentDocumentsView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request):
        prn = request.query_params.get("prn", "").strip().upper()
        if not prn:
            raise ValidationError({"prn": "Enter a student PRN to load their document checklist."})
        try:
            student = StudentRecord.objects.get(prn=prn)
        except StudentRecord.DoesNotExist as exc:
            raise NotFound("No student record found for this PRN.") from exc
        AuditLog.objects.create(actor=request.user, action="staff.student_documents.viewed", target_type="StudentRecord",
                                target_id=str(student.pk), details={"prn": student.prn})
        documents = StudentDocument.objects.filter(student=student).order_by("kind", "-uploaded_at")
        rows = [{"id": doc.pk, "prn": student.prn, "student_name": student.full_name,
                 "year_level": student.year_level, "department": student.department,
                 "kind": doc.kind, "file_name": Path(doc.file.name).name,
                 "review_status": doc.review_status, "ocr_status": doc.ocr_status,
                 "validation_score": doc.validation_score, "issue_date": doc.issue_date,
                 "expiry_date": doc.expiry_date, "validation_reasons": doc.validation_reasons,
                 "extracted_fields": doc.extracted_fields, "is_staff_reference": doc.application_id is None,
                 "uploaded_at": doc.uploaded_at} for doc in documents]
        return Response({"student": {"prn": student.prn, "full_name": student.full_name,
                                      "year_level": student.year_level, "department": student.department},
                         "documents": rows})

    def post(self, request):
        incoming = StaffStudentDocumentUploadSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        values = incoming.validated_data
        try:
            student = StudentRecord.objects.get(prn=values["prn"])
        except StudentRecord.DoesNotExist as exc:
            raise NotFound("No student record found for this PRN. Add the student record first.") from exc
        document = StudentDocument.objects.create(student=student, kind=values["kind"], file=values["file"])
        from .ocr_services import verify_document
        run = verify_document(document)
        AuditLog.objects.create(actor=request.user, action="staff.student_document.uploaded", target_type="StudentDocument",
                                target_id=str(document.pk), details={"prn": student.prn, "kind": document.kind,
                                                                    "ocr_status": document.ocr_status,
                                                                    "score": str(run.score) if run else None})
        return Response({"id": document.pk, "prn": student.prn, "student_name": student.full_name,
                         "year_level": student.year_level, "department": student.department,
                         "kind": document.kind, "file_name": Path(document.file.name).name,
                         "review_status": document.review_status, "ocr_status": document.ocr_status,
                         "validation_score": document.validation_score, "issue_date": document.issue_date,
                         "expiry_date": document.expiry_date, "validation_reasons": document.validation_reasons,
                         "extracted_fields": document.extracted_fields, "is_staff_reference": True,
                         "uploaded_at": document.uploaded_at}, status=status.HTTP_201_CREATED)


class StudentApplicationsView(APIView):
    def get(self, request):
        try:
            student = request.user.student_record
        except ObjectDoesNotExist:
            return Response({"detail": "No staff-uploaded student record is linked to this account."}, status=404)
        applications = Application.objects.filter(student=student).order_by("-created_at")
        return Response(StudentApplicationSerializer(applications, many=True).data)

    def post(self, request):
        serializer = StudentApplicationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        AuditLog.objects.create(actor=request.user, action="application.created", target_type="Application",
                                target_id=str(application.pk), details={"academic_year": application.academic_year,
                                                                       "entry_year": application.entry_year})
        return Response(StudentApplicationSerializer(application).data, status=status.HTTP_201_CREATED)


class StaffDocumentReviewView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request, document_id=None):
        queryset = StudentDocument.objects.select_related("student", "application").order_by("review_status", "-uploaded_at")
        if document_id:
            queryset = queryset.filter(pk=document_id)
        else:
            state = request.query_params.get("status")
            if state in StudentDocument.ReviewStatus.values:
                queryset = queryset.filter(review_status=state)
        rows = [{"id": doc.pk, "prn": doc.student.prn, "student_name": doc.student.full_name, "kind": doc.kind,
                 "file_name": Path(doc.file.name).name, "review_status": doc.review_status, "ocr_status": doc.ocr_status,
                 "ocr_confidence": doc.ocr_confidence, "validation_score": doc.validation_score,
                 "extracted_fields": doc.extracted_fields, "validation_reasons": doc.validation_reasons,
                 "issue_date": doc.issue_date, "expiry_date": doc.expiry_date, "staff_note": doc.staff_note,
                 "uploaded_at": doc.uploaded_at} for doc in queryset[:200]]
        if document_id and not rows:
            return Response({"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(rows[0] if document_id else rows)

    def patch(self, request, document_id):
        try:
            document = StudentDocument.objects.get(pk=document_id)
        except StudentDocument.DoesNotExist:
            return Response({"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND)
        allowed = {StudentDocument.ReviewStatus.VERIFIED, StudentDocument.ReviewStatus.MANUAL,
                   StudentDocument.ReviewStatus.NEEDS_REUPLOAD}
        new_status = request.data.get("review_status")
        if new_status not in allowed:
            raise ValidationError({"review_status": "Choose VERIFIED, MANUAL, or NEEDS_REUPLOAD."})
        note = request.data.get("staff_note", "")
        if not isinstance(note, str) or len(note) > 2000:
            raise ValidationError({"staff_note": "Staff note must be 2,000 characters or fewer."})
        document.review_status = new_status
        document.staff_note = note
        document.save(update_fields=["review_status", "staff_note"])
        AuditLog.objects.create(actor=request.user, action="document.staff_review", target_type="StudentDocument",
                                target_id=str(document.pk), details={"review_status": new_status})
        return self.get(request, document_id)


class StaffDocumentDownloadView(APIView):
    permission_classes = [IsStaffUser]

    def get(self, request, document_id):
        try:
            document = StudentDocument.objects.get(pk=document_id)
            document.file.open("rb")
        except (StudentDocument.DoesNotExist, OSError):
            raise NotFound("Document file not found.")
        AuditLog.objects.create(actor=request.user, action="document.staff_download", target_type="StudentDocument", target_id=str(document.pk))
        return FileResponse(document.file, as_attachment=True, filename=Path(document.file.name).name)

class ShareholderReviewViewSet(viewsets.ModelViewSet):
    queryset = ShareholderClaim.objects.select_related("application", "application__student")
    serializer_class = ShareholderClaimSerializer
    permission_classes = [IsStaffUser]
    http_method_names = ["get", "patch", "head", "options"]
    def perform_update(self, serializer):
        from django.utils import timezone
        serializer.save(reviewed_by=self.request.user, reviewed_at=timezone.now())
