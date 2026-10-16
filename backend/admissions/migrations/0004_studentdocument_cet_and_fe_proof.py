from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("admissions", "0003_studentrecord_year_level")]

    operations = [
        migrations.AlterField(
            model_name="studentdocument",
            name="kind",
            field=models.CharField(max_length=32, choices=[
                ("PASSPORT_PHOTO", "Passport-size photo"),
                ("PRN_PROOF", "PRN proof"),
                ("CET_RESULT", "CET result"),
                ("FE_ADMISSION_PROOF", "FE admission proof / admission form"),
                ("MARKSHEET", "Previous year / semester marksheet"),
                ("AADHAAR", "Aadhaar card"),
                ("CASTE", "Caste certificate"),
                ("CASTE_VALIDITY", "Caste validity certificate"),
                ("NCL", "Non-creamy layer certificate"),
                ("DOMICILE", "Domicile certificate"),
                ("RATION_CARD", "Ration card"),
                ("SSC_MARKSHEET", "10th marksheet"),
                ("HSC_MARKSHEET", "12th marksheet"),
                ("ELIGIBILITY", "First-year admission eligibility form"),
                ("LEAVING_CERTIFICATE", "12th leaving certificate"),
                ("SCHOLARSHIP_PROOF", "Scholarship application / approval proof"),
                ("INCOME_CERTIFICATE", "Income certificate"),
                ("OTHER", "Other"),
            ]),
        ),
    ]
