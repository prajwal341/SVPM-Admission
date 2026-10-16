from django.db import migrations, models


def assign_existing_levels(apps, schema_editor):
    StudentRecord = apps.get_model("admissions", "StudentRecord")
    Application = apps.get_model("admissions", "Application")
    database = schema_editor.connection.alias
    level_by_entry_year = {2: "SE", 3: "TE", 4: "BE"}
    for student in StudentRecord.objects.using(database).all().iterator():
        latest = Application.objects.using(database).filter(student_id=student.pk).order_by("-created_at").first()
        if latest and latest.entry_year in level_by_entry_year:
            StudentRecord.objects.using(database).filter(pk=student.pk).update(year_level=level_by_entry_year[latest.entry_year])


class Migration(migrations.Migration):
    dependencies = [("admissions", "0002_studentdocument_ocr")]

    operations = [
        migrations.AddField(
            model_name="studentrecord",
            name="year_level",
            field=models.CharField(
                choices=[("FE", "First year (FE)"), ("SE", "Second year (SE)"),
                         ("TE", "Third year (TE)"), ("BE", "Fourth year (BE)")],
                default="FE",
                max_length=2,
            ),
        ),
        migrations.RunPython(assign_existing_levels, migrations.RunPython.noop),
    ]
