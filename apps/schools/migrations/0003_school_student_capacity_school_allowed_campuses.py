from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0002_remove_school_subdomain_school_address_school_city_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="allowed_campuses",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="school",
            name="student_capacity",
            field=models.PositiveIntegerField(default=1000),
        ),
    ]
