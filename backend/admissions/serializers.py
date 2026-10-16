import re
from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist
from .models import Application, ShareholderClaim, StudentDocument, StudentRecord


class StaffStudentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentRecord
        fields = ["id", "prn", "full_name", "email", "mobile", "department", "year_level",
                  "first_year_admission", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_prn(self, value):
        return value.strip().upper()

    def validate_email(self, value):
        return value.strip().lower()

    def validate_mobile(self, value):
        digits = re.sub(r"\D", "", value)
        digits = digits[2:] if digits.startswith("91") and len(digits) == 12 else digits
        if len(digits) != 10:
            raise serializers.ValidationError("Enter a 10-digit Indian mobile number.")
        return digits

    def validate_full_name(self, value):
        return " ".join(value.split())


class StudentApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ["id", "academic_year", "entry_year", "department", "gender", "category", "admission_route",
                  "has_ebc_ews_certificate", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]

    def validate_academic_year(self, value):
        value = value.replace("–", "-").replace("—", "-").strip()
        if not re.fullmatch(r"\d{4}-\d{2,4}", value):
            raise serializers.ValidationError("Use an academic year such as 2026-27.")
        return value

    def validate(self, attrs):
        try:
            student = self.context["request"].user.student_record
        except ObjectDoesNotExist as exc:
            raise serializers.ValidationError("No staff-uploaded student record is linked to this account.") from exc
        if Application.objects.filter(student=student, academic_year=attrs["academic_year"], entry_year=attrs["entry_year"]).exists():
            raise serializers.ValidationError("An application already exists for this admission year.")
        return attrs

    def create(self, validated_data):
        return Application.objects.create(student=self.context["request"].user.student_record, **validated_data)


class StudentDocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentDocument
        fields = ["id", "application", "kind", "file", "ocr_status", "ocr_confidence", "extracted_fields",
                  "validation_score", "validation_reasons", "issue_date", "expiry_date", "review_status", "uploaded_at"]
        read_only_fields = ["id", "ocr_status", "ocr_confidence", "extracted_fields", "validation_score",
                            "validation_reasons", "issue_date", "expiry_date", "review_status", "uploaded_at"]

    def validate_file(self, value):
        if value.size > 3 * 1024 * 1024:
            raise serializers.ValidationError("File must be 3 MB or smaller.")
        name = value.name.lower()
        if not name.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff", ".pdf")):
            raise serializers.ValidationError("Upload a JPG, PNG, TIFF, or PDF file.")
        header = value.read(8)
        value.seek(0)
        valid_image = header.startswith(b"\xff\xd8\xff") or header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith((b"II*\x00", b"MM\x00*"))
        valid_pdf = header.startswith(b"%PDF-")
        if not (valid_image or valid_pdf):
            raise serializers.ValidationError("The file content does not match a supported image or PDF.")
        return value

    def validate_application(self, value):
        request = self.context["request"]
        try:
            student = request.user.student_record
        except ObjectDoesNotExist:
            raise serializers.ValidationError("No staff-uploaded student record is linked to this account.")
        if value.student_id != student.pk:
            raise serializers.ValidationError("You can only upload documents to your own application.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["student"] = request.user.student_record
        return super().create(validated_data)


class StaffStudentDocumentUploadSerializer(serializers.Serializer):
    prn = serializers.CharField(max_length=32)
    kind = serializers.ChoiceField(choices=StudentDocument.Kind.choices)
    file = serializers.FileField()

    def validate_prn(self, value):
        return value.strip().upper()

    def validate_file(self, value):
        if value.size > 3 * 1024 * 1024:
            raise serializers.ValidationError("File must be 3 MB or smaller.")
        name = value.name.lower()
        if not name.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff", ".pdf")):
            raise serializers.ValidationError("Upload a JPG, PNG, TIFF, or PDF file.")
        header = value.read(8)
        value.seek(0)
        valid_image = header.startswith(b"\xff\xd8\xff") or header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith((b"II*\x00", b"MM\x00*"))
        valid_pdf = header.startswith(b"%PDF-")
        if not (valid_image or valid_pdf):
            raise serializers.ValidationError("The file content does not match a supported image or PDF.")
        return value


class FeeEstimateInputSerializer(serializers.Serializer):
    category = serializers.CharField(max_length=24)
    gender = serializers.CharField(max_length=12)
    has_ebc_ews_certificate = serializers.BooleanField(required=False, default=False)
    carried_balance = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False, default=0)


class RegistrationStartSerializer(serializers.Serializer):
    prn = serializers.CharField(max_length=32)
    full_name = serializers.CharField(max_length=180)
    email = serializers.EmailField()
    mobile = serializers.CharField(max_length=20)
    entry_year = serializers.ChoiceField(choices=[2, 3, 4])
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)


class RegistrationVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    email_code = serializers.RegexField(r"^\d{6}$")
    mobile_code = serializers.RegexField(r"^\d{6}$")


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)


class PasswordResetStartSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=180)


class PasswordResetCompleteSerializer(RegistrationVerifySerializer):
    new_password = serializers.CharField(min_length=8, max_length=128, write_only=True)


class ShareholderClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareholderClaim
        fields = ["id", "application", "shareholder_name", "member_number", "relationship", "affidavit", "sugarcane_bill", "status", "staff_note", "reviewed_by", "reviewed_at", "created_at"]
        read_only_fields = ["reviewed_by", "reviewed_at", "created_at"]
