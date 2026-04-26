from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schools", "0014_subscription_coupons"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriptioninvoice",
            name="tax_percent",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="subscriptioninvoice",
            name="tax_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="subscriptioninvoice",
            name="total_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]

