from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
import re
import uuid


class StudentRecord(models.Model):
    """Staff-managed baseline record; Aadhaar itself is never stored in plaintext."""
    class YearLevel(models.TextChoices):
        FE = "FE", "First year (FE)"
        SE = "SE", "Second year (SE)"
        TE = "TE", "Third year (TE)"
        BE = "BE", "Fourth year (BE)"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="student_record")
    prn = models.CharField(max_length=32, unique=True)
    full_name = models.CharField(max_length=180)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=20, unique=True)
    aadhaar_digest = models.CharField(max_length=64, unique=True, null=True, blank=True)
    aadhaar_last4 = models.CharField(max_length=4, blank=True)
    department = models.CharField(max_length=100)
    year_level = models.CharField(max_length=2, choices=YearLevel.choices, default=YearLevel.FE)
    first_year_admission = models.CharField(max_length=9, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def save(self, *args, **kwargs):
        self.prn = self.prn.strip().upper()
        self.email = self.email.strip().lower()
        digits = re.sub(r"\D", "", self.mobile)
        self.mobile = digits[2:] if digits.startswith("91") and len(digits) == 12 else digits
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.prn})"


class Application(models.Model):
    class EntryYear(models.IntegerChoices):
        SECOND = 2, "2nd year"
        THIRD = 3, "3rd year"
        FOURTH = 4, "4th year"

    class Gender(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"
        OTHER = "O", "Other"

    class Route(models.TextChoices):
        CAP = "CAP", "CAP round"
        MANAGEMENT = "MANAGEMENT", "Management / other"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        DOCUMENT_REVIEW = "DOCUMENT_REVIEW", "Document review"
        STAFF_REVIEW = "STAFF_REVIEW", "Manual staff review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    student = models.ForeignKey(StudentRecord, on_delete=models.PROTECT, related_name="applications")
    academic_year = models.CharField(max_length=9)
    entry_year = models.PositiveSmallIntegerField(choices=EntryYear.choices)
    department = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=Gender.choices)
    category = models.CharField(max_length=24)
    admission_route = models.CharField(max_length=12, choices=Route.choices)
    has_ebc_ews_certificate = models.BooleanField(default=False)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.prn} · {self.academic_year}"


class StudentDocument(models.Model):
    class Kind(models.TextChoices):
        PASSPORT_PHOTO = "PASSPORT_PHOTO", "Passport-size photo"
        PRN_PROOF = "PRN_PROOF", "PRN proof"
        CET_RESULT = "CET_RESULT", "CET result"
        FE_ADMISSION_PROOF = "FE_ADMISSION_PROOF", "FE admission proof / admission form"
        MARKSHEET = "MARKSHEET", "Previous year / semester marksheet"
        AADHAAR = "AADHAAR", "Aadhaar card"
        CASTE = "CASTE", "Caste certificate"
        CASTE_VALIDITY = "CASTE_VALIDITY", "Caste validity certificate"
        NCL = "NCL", "Non-creamy layer certificate"
        DOMICILE = "DOMICILE", "Domicile certificate"
        RATION_CARD = "RATION_CARD", "Ration card"
        SSC_MARKSHEET = "SSC_MARKSHEET", "10th marksheet"
        HSC_MARKSHEET = "HSC_MARKSHEET", "12th marksheet"
        ELIGIBILITY = "ELIGIBILITY", "First-year admission eligibility form"
        LEAVING_CERTIFICATE = "LEAVING_CERTIFICATE", "12th leaving certificate"
        SCHOLARSHIP_PROOF = "SCHOLARSHIP_PROOF", "Scholarship application / approval proof"
        INCOME_CERTIFICATE = "INCOME_CERTIFICATE", "Income certificate"
        OTHER = "OTHER", "Other"

    class ReviewStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        AUTO_CHECK = "AUTO_CHECK", "Automated checks passed"
        VERIFIED = "VERIFIED", "Verified"
        MANUAL = "MANUAL", "Manual review"
        NEEDS_REUPLOAD = "NEEDS_REUPLOAD", "Needs re-upload"

    class OCRStatus(models.TextChoices):
        PENDING = "PENDING", "Pending OCR"
        COMPLETED = "COMPLETED", "OCR completed"
        UNAVAILABLE = "UNAVAILABLE", "OCR unavailable"
        FAILED = "FAILED", "OCR failed"

    student = models.ForeignKey(StudentRecord, on_delete=models.PROTECT, related_name="documents")
    application = models.ForeignKey(Application, null=True, blank=True, on_delete=models.PROTECT, related_name="documents")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    file = models.FileField(upload_to="student-documents/%Y/%m/")
    review_status = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    ocr_status = models.CharField(max_length=16, choices=OCRStatus.choices, default=OCRStatus.PENDING)
    ocr_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    extracted_fields = models.JSONField(default=dict, blank=True)
    validation_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    validation_reasons = models.JSONField(default=list, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    ocr_processed_at = models.DateTimeField(null=True, blank=True)
    staff_note = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class ScholarshipRecord(models.Model):
    class Status(models.TextChoices):
        NOT_APPLIED = "NOT_APPLIED", "Not applied"
        APPLIED = "APPLIED", "Applied"
        APPROVED = "APPROVED", "Approved"
        CREDITED = "CREDITED", "Credited to college"
        REJECTED = "REJECTED", "Rejected"

    application = models.OneToOneField(Application, on_delete=models.PROTECT, related_name="scholarship")
    scheme_name = models.CharField(max_length=120, default="MahaDBT")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.APPLIED)
    proof = models.FileField(upload_to="scholarship-proofs/%Y/%m/", blank=True)
    amount_approved = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount_credited = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class FeeAssessment(models.Model):
    application = models.OneToOneField(Application, on_delete=models.PROTECT, related_name="fee_assessment")
    schedule_year = models.CharField(max_length=9, default="2025-26")
    fee_group = models.CharField(max_length=80)
    base_fee = models.DecimalField(max_digits=10, decimal_places=2)
    scholarship_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    carried_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    confirmed_at = models.DateTimeField(null=True, blank=True)


class Payment(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid and verified"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    assessment = models.ForeignKey(FeeAssessment, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    gateway = models.CharField(max_length=24, default="RAZORPAY")
    gateway_order_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    gateway_payment_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CREATED)
    gateway_signature_verified = models.BooleanField(default=False)
    receipt_reference = models.CharField(max_length=80, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class OTPChallenge(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        SMS = "SMS", "Mobile SMS"
    class Purpose(models.TextChoices):
        REGISTER = "REGISTER", "First registration"
        PASSWORD_RESET = "PASSWORD_RESET", "Password reset"

    email = models.EmailField()
    mobile = models.CharField(max_length=20)
    challenge_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    channel = models.CharField(max_length=8, choices=Channel.choices)
    code_digest = models.CharField(max_length=64)
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RegistrationIntent(models.Model):
    challenge_id = models.UUIDField(unique=True, default=uuid.uuid4)
    prn = models.CharField(max_length=32)
    full_name = models.CharField(max_length=180)
    email = models.EmailField()
    mobile = models.CharField(max_length=20)
    entry_year = models.PositiveSmallIntegerField(choices=Application.EntryYear.choices)
    password_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PasswordResetIntent(models.Model):
    challenge_id = models.UUIDField(unique=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ShareholderClaim(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending manual review"
        MORE_INFO = "MORE_INFO", "More documents required"
        VERIFIED = "VERIFIED", "Documents verified · office processing"
        NOT_ELIGIBLE = "NOT_ELIGIBLE", "Not eligible"
        SETTLED = "SETTLED", "Settled through sugarcane bill"

    application = models.OneToOneField(Application, on_delete=models.PROTECT, related_name="shareholder_claim")
    shareholder_name = models.CharField(max_length=180)
    member_number = models.CharField(max_length=64)
    relationship = models.CharField(max_length=60)
    affidavit = models.FileField(upload_to="shareholder-affidavits/%Y/%m/")
    sugarcane_bill = models.FileField(upload_to="shareholder-bills/%Y/%m/")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    staff_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_shareholder_claims")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class VerificationRun(models.Model):
    class Decision(models.TextChoices):
        AUTO_CHECK = "AUTO_CHECK", "Passed automated checks"
        MANUAL_REVIEW = "MANUAL_REVIEW", "Manual review"
        FAILED = "FAILED", "Failed hard check"

    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="verification_runs")
    document = models.ForeignKey(StudentDocument, null=True, blank=True, on_delete=models.PROTECT, related_name="verification_runs")
    score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    threshold = models.DecimalField(max_digits=5, decimal_places=2, default=90)
    decision = models.CharField(max_length=16, choices=Decision.choices)
    reasons = models.JSONField(default=list, blank=True)
    provider = models.CharField(max_length=80, blank=True)
    model_version = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
