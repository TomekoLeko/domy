from django.db import migrations, models


def map_beneficiary_to_order(apps, schema_editor):
    Payment = apps.get_model('finance', 'Payment')
    Payment.objects.filter(payment_type='beneficiary').update(payment_type='order')


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0010_monthlycontributionusage'),
    ]

    operations = [
        migrations.RunPython(map_beneficiary_to_order, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='payment',
            name='payment_type',
            field=models.CharField(
                choices=[
                    ('contribution', 'Wpłata od wspierającego'),
                    ('order', 'Płatność za zamówienie'),
                    ('refund', 'Zwrot środków'),
                    ('expense', 'Wydatek'),
                    ('other', 'Inne'),
                    ('invoice', 'Faktura'),
                ],
                max_length=30,
                verbose_name='Typ płatności',
            ),
        ),
    ]
