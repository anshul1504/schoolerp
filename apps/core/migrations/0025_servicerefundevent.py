from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0019_phase2_student_ops_models"),
        ("fees", "0001_initial"),
        ("core", "0024_inventoryvendor_inventorypurchaseorder"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceRefundEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("service_type", models.CharField(choices=[("TRANSPORT", "Transport"), ("HOSTEL", "Hostel")], max_length=20)),
                ("source", models.CharField(blank=True, max_length=40)),
                ("source_ref", models.CharField(blank=True, max_length=64)),
                ("billed_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("paid_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("policy_ratio", models.DecimalField(decimal_places=4, default=0, max_digits=6)),
                ("days_remaining", models.PositiveIntegerField(default=0)),
                ("total_days", models.PositiveIntegerField(default=0)),
                ("recommended_refund", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("SETTLED", "Settled")], default="OPEN", max_length=20)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("fee_ledger", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="service_refund_events", to="fees.studentfeeledger")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_refund_events", to="schools.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_refund_events", to="students.student")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
