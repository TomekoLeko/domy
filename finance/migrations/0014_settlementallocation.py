# Generated manually for SettlementAllocation

import django.core.validators
from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0013_order_payment_status'),
        ('finance', '0013_payment_payment_method'),
    ]

    operations = [
        migrations.CreateModel(
            name='SettlementAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'allocated_amount',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(Decimal('0'))],
                        verbose_name='Kwota przypisana do pozycji',
                    ),
                ),
                (
                    'order_item',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='settlement_allocations',
                        to='products.orderitem',
                        verbose_name='Pozycja zamówienia',
                    ),
                ),
                (
                    'payment',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='settlement_allocations',
                        to='finance.payment',
                        verbose_name='Płatność',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Alokacja rozliczenia',
                'verbose_name_plural': 'Alokacje rozliczeń',
            },
        ),
        migrations.AddIndex(
            model_name='settlementallocation',
            index=models.Index(fields=['payment'], name='finance_sett_payment_6b5fbd_idx'),
        ),
        migrations.AddIndex(
            model_name='settlementallocation',
            index=models.Index(fields=['order_item'], name='finance_sett_order_it_0a8b2e_idx'),
        ),
        migrations.AddConstraint(
            model_name='settlementallocation',
            constraint=models.UniqueConstraint(
                fields=('payment', 'order_item'),
                name='finance_settlementallocation_payment_orderitem_uniq',
            ),
        ),
    ]
