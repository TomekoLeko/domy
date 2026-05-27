from django.db import migrations, models


def migrate_is_service_to_type(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(is_service=True).update(type='shipment')
    Product.objects.filter(is_service=False).update(type='item')


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0016_product_is_service_exclude_from_catalog'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='type',
            field=models.CharField(
                choices=[
                    ('item', 'Towar'),
                    ('shipment', 'Wysyłka'),
                    ('service', 'Usługa'),
                ],
                default='item',
                max_length=20,
                verbose_name='Typ',
            ),
        ),
        migrations.RunPython(migrate_is_service_to_type, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='product',
            name='is_service',
        ),
    ]
