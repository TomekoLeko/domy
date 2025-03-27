# Generated by Django 5.1.3 on 2025-03-21 15:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0008_alter_invoice_net_price_alter_invoice_vat_rate'),
        ('products', '0008_alter_order_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='related_order_items',
            field=models.ManyToManyField(blank=True, related_name='payments', to='products.orderitem', verbose_name='Powiązane elementy zamówienia'),
        ),
    ]
