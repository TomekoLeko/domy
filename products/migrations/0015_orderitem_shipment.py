import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0014_productcategory_icon'),
        ('shipping', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='shipment',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='items',
                to='shipping.shipment',
                verbose_name='Wysyłka',
            ),
        ),
    ]
