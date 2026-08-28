from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0018_order_order_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='volume_unit',
            field=models.CharField(
                choices=[
                    ('l', 'Litry'),
                    ('ml', 'Mililitry'),
                    ('kg', 'Kilogramy'),
                    ('pcs', 'Sztuki'),
                ],
                default='pcs',
                max_length=10,
            ),
        ),
    ]
