# Generated for the local OCR document-review workflow.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("admissions", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="studentdocument",
            name="review_status",
            field=models.CharField(max_length=16, default="PENDING", choices=[
                ("PENDING", "Pending"), ("AUTO_CHECK", "Automated checks passed"),
                ("VERIFIED", "Verified"), ("MANUAL", "Manual review"), ("NEEDS_REUPLOAD", "Needs re-upload"),
            ]),
        ),
        migrations.AlterField(
            model_name="studentdocument",
            name="kind",
            field=models.CharField(max_length=32, choices=[
                ("PASSPORT_PHOTO", "Passport-size photo"), ("PRN_PROOF", "PRN proof"),
                ("MARKSHEET", "Previous year / semester marksheet"), ("AADHAAR", "Aadhaar card"),
                ("CASTE", "Caste certificate"), ("CASTE_VALIDITY", "Caste validity certificate"),
                ("NCL", "Non-creamy layer certificate"), ("DOMICILE", "Domicile certificate"),
                ("RATION_CARD", "Ration card"), ("SSC_MARKSHEET", "10th marksheet"),
                ("HSC_MARKSHEET", "12th marksheet"), ("ELIGIBILITY", "First-year admission eligibility form"),
                ("LEAVING_CERTIFICATE", "12th leaving certificate"),
                ("SCHOLARSHIP_PROOF", "Scholarship application / approval proof"),
                ("INCOME_CERTIFICATE", "Income certificate"), ("OTHER", "Other"),
            ]),
        ),
        migrations.AddField(
            model_name="studentdocument", name="ocr_status",
            field=models.CharField(max_length=16, default="PENDING", choices=[
                ("PENDING", "Pending OCR"), ("COMPLETED", "OCR completed"),
                ("UNAVAILABLE", "OCR unavailable"), ("FAILED", "OCR failed"),
            ]),
        ),
        migrations.AddField(model_name="studentdocument", name="ocr_confidence", field=models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name="studentdocument", name="extracted_fields", field=models.JSONField(default=dict, blank=True)),
        migrations.AddField(model_name="studentdocument", name="validation_score", field=models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)),
        migrations.AddField(model_name="studentdocument", name="validation_reasons", field=models.JSONField(default=list, blank=True)),
        migrations.AddField(model_name="studentdocument", name="issue_date", field=models.DateField(null=True, blank=True)),
        migrations.AddField(model_name="studentdocument", name="expiry_date", field=models.DateField(null=True, blank=True)),
        migrations.AddField(model_name="studentdocument", name="ocr_processed_at", field=models.DateTimeField(null=True, blank=True)),
    ]
