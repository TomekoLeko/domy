from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_remove_orderitem_quantity_remove_orderitem_subtotal'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='max_payable_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
