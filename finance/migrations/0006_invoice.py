# Generated by Django 5.1.3 on 2025-03-06 11:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0005_payment_sender'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_number', models.CharField(max_length=50, unique=True)),
                ('net_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('vat_rate', models.DecimalField(decimal_places=2, max_digits=4)),
                ('gross_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('supplier_name', models.CharField(max_length=255)),
                ('supplier_address', models.CharField(max_length=255)),
                ('supplier_postal', models.CharField(max_length=10)),
                ('supplier_city', models.CharField(max_length=100)),
                ('supplier_nip', models.CharField(max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Faktura',
                'verbose_name_plural': 'Faktury',
                'ordering': ['-created_at'],
            },
        ),
    ]
