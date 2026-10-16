from django.contrib import admin
from .models import Application, AuditLog, FeeAssessment, OTPChallenge, Payment, ScholarshipRecord, ShareholderClaim, StudentDocument, StudentRecord, VerificationRun


@admin.register(StudentRecord)
class StudentRecordAdmin(admin.ModelAdmin):
    list_display = ("prn", "full_name", "year_level", "department", "email", "mobile")
    list_filter = ("year_level", "department")
    search_fields = ("prn", "full_name", "email", "mobile")
    readonly_fields = ("aadhaar_digest", "aadhaar_last4", "created_at", "updated_at")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("student", "academic_year", "entry_year", "category", "admission_route", "status")
    list_filter = ("academic_year", "entry_year", "category", "admission_route", "status")
    search_fields = ("student__prn", "student__full_name")


@admin.register(ShareholderClaim)
class ShareholderClaimAdmin(admin.ModelAdmin):
    list_display = ("application", "shareholder_name", "member_number", "status", "reviewed_by", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("application__student__prn", "shareholder_name", "member_number")
    readonly_fields = ("created_at",)


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ("student", "kind", "review_status", "ocr_status", "validation_score", "issue_date", "expiry_date", "uploaded_at")
    list_filter = ("kind", "review_status", "ocr_status")
    search_fields = ("student__prn", "student__full_name", "application__academic_year")
    readonly_fields = ("ocr_status", "ocr_confidence", "extracted_fields", "validation_score", "validation_reasons", "issue_date", "expiry_date", "ocr_processed_at", "uploaded_at")


admin.site.register([ScholarshipRecord, FeeAssessment, Payment, OTPChallenge, VerificationRun, AuditLog])
