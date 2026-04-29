import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_transportassignment_hostelallocation"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryVendor",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=160)),
                ("contact_person", models.CharField(blank=True, max_length=120)),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("gstin", models.CharField(blank=True, max_length=30)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_vendors",
                        to="schools.school",
                    ),
                ),
            ],
            options={
                "ordering": ["school__name", "name", "-id"],
                "unique_together": {("school", "name")},
            },
        ),
        migrations.CreateModel(
            name="InventoryPurchaseOrder",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("po_number", models.CharField(max_length=40)),
                ("quantity", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("unit_cost", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("PLACED", "Placed"),
                            ("RECEIVED", "Received"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="PLACED",
                        max_length=20,
                    ),
                ),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("ordered_on", models.DateField(auto_now_add=True)),
                ("received_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="purchase_orders",
                        to="core.inventoryitem",
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_purchase_orders",
                        to="schools.school",
                    ),
                ),
                (
                    "vendor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="purchase_orders",
                        to="core.inventoryvendor",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "unique_together": {("school", "po_number")},
            },
        ),
    ]
