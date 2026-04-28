from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0011_remove_beneficiary_payment_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="monthlycontributionusage",
            name="discount_rate_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("100.00"),
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
    ]
