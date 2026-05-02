from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0012_monthlycontributionusage_discount_rate_percent"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("transfer", "Przelew"),
                    ("cash", "Gotówka"),
                    ("cod", "Pobranie"),
                    ("card", "Karta"),
                    ("blik", "BLIK"),
                ],
                default="transfer",
                max_length=20,
                verbose_name="Sposób zapłaty",
            ),
        ),
    ]
