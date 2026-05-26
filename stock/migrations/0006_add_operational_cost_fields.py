from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0005_stockreduction_order_item'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockentry',
            name='receiving_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name='Koszt obsługi przyjęcia',
            ),
        ),
        migrations.AddField(
            model_name='stockreduction',
            name='issuing_cost',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name='Koszt obsługi wydania',
            ),
        ),
    ]
