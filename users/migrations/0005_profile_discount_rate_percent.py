from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_profile_monthly_limit"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="discount_rate_percent",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Procent ulgi dla beneficjenta (0-100)",
                max_digits=5,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
    ]
