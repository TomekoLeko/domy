# Generated by Django 5.1.3 on 2025-02-18 13:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0003_alter_payment_payment_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='payment_type',
            field=models.CharField(choices=[('contribution', 'Wpłata od wspierającego'), ('order', 'Płatność za zamówienie'), ('beneficiary', 'Zamówienie beneficjenta'), ('refund', 'Zwrot środków'), ('expense', 'Wydatek'), ('other', 'Inne'), ('invoice', 'Faktura')], max_length=30, verbose_name='Typ płatności'),
        ),
    ]
