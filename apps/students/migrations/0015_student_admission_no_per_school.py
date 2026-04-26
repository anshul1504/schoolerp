from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0008_student_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="student",
            name="admission_no",
            field=models.CharField(max_length=30),
        ),
        migrations.AddConstraint(
            model_name="student",
            constraint=models.UniqueConstraint(fields=("school", "admission_no"), name="uniq_student_admission_no_per_school"),
        ),
    ]
