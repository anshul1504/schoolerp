from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_rename_core_entity_entity_3f0f6d_idx_core_entity_entity_128ade_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlogexport",
            name="immutable_copy_path",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]

