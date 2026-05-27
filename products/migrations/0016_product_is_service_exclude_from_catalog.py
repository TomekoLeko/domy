from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0015_orderitem_shipment'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='exclude_from_catalog',
            field=models.BooleanField(default=False, verbose_name='Ukryj w katalogu sklepu'),
        ),
        migrations.AddField(
            model_name='product',
            name='is_service',
            field=models.BooleanField(
                default=False,
                help_text='Np. dostawa — nie jest towarem magazynowym.',
                verbose_name='Usługa',
            ),
        ),
    ]
