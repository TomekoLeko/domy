from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0015_remove_monthlycontributionusage_order_items'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='lob',
            field=models.CharField(
                blank=True,
                choices=[
                    ('foster', 'Wspieramy'),
                    ('clothes', 'Ubrania'),
                    ('it', 'Programowanie'),
                ],
                max_length=20,
                null=True,
                verbose_name='Linia działalności',
            ),
        ),
        migrations.AlterField(
            model_name='payment',
            name='payment_type',
            field=models.CharField(
                choices=[
                    ('contribution', 'Wsparcie'),
                    ('order', 'Zamówienie'),
                    ('refund', 'Zwrot'),
                    ('expense', 'Wydatek'),
                    ('other', 'Inne'),
                    ('invoice', 'Faktura'),
                ],
                max_length=30,
                verbose_name='Typ płatności',
            ),
        ),
    ]
