from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Shipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('carrier', models.CharField(choices=[('inpost', 'InPost'), ('dpd', 'DPD')], max_length=20, verbose_name='Dostawca')),
                ('delivery_method', models.CharField(choices=[('courier', 'Kurier'), ('parcel_locker', 'Paczkomat')], max_length=20, verbose_name='Typ dostawy')),
                ('tracking_number', models.CharField(blank=True, max_length=64, verbose_name='Numer listu przewozowego')),
                ('notes', models.TextField(blank=True, verbose_name='Uwagi')),
                ('recipient_name', models.CharField(max_length=200, verbose_name='Imię i nazwisko odbiorcy')),
                ('recipient_phone', models.CharField(max_length=32, verbose_name='Telefon odbiorcy')),
                ('recipient_email', models.EmailField(blank=True, max_length=254, verbose_name='E-mail odbiorcy')),
                ('recipient_postal_code', models.CharField(max_length=10, verbose_name='Kod pocztowy odbiorcy')),
                ('recipient_address', models.CharField(max_length=255, verbose_name='Adres (ulica, nr domu, nr mieszkania)')),
                ('recipient_city', models.CharField(max_length=100, verbose_name='Miasto odbiorcy')),
                ('parcel_locker_code', models.CharField(blank=True, max_length=20, verbose_name='Numer paczkomatu')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Wysyłka',
                'verbose_name_plural': 'Wysyłki',
                'ordering': ['-created_at'],
            },
        ),
    ]
