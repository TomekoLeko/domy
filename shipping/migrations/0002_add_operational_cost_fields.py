from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shipping', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='shipping_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name='Koszt wysyłki',
            ),
        ),
        migrations.AddField(
            model_name='shipment',
            name='packaging_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name='Koszt pakowania',
            ),
        ),
    ]
