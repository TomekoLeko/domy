from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0012_order_max_payable_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("pending", "Oczekujące na rozliczenie"),
                    ("processing", "W trakcie rozliczenia"),
                    ("partial", "Częściowo opłacone"),
                    ("paid", "Opłacone"),
                    ("rejected", "Odrzucone"),
                    ("cancelled", "Rozliczenie anulowane"),
                ],
                default="pending",
                max_length=20,
                verbose_name="Status rozliczenia",
            ),
        ),
    ]
