from django.db import models


class Carrier(models.TextChoices):
    INPOST = 'inpost', 'InPost'
    DPD = 'dpd', 'DPD'


class DeliveryMethod(models.TextChoices):
    COURIER = 'courier', 'Kurier'
    PARCEL_LOCKER = 'parcel_locker', 'Paczkomat'


class Shipment(models.Model):
    carrier = models.CharField(
        max_length=20,
        choices=Carrier.choices,
        verbose_name='Dostawca',
    )
    delivery_method = models.CharField(
        max_length=20,
        choices=DeliveryMethod.choices,
        verbose_name='Typ dostawy',
    )

    tracking_number = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Numer listu przewozowego',
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Uwagi',
    )

    recipient_name = models.CharField(
        max_length=200,
        verbose_name='Imię i nazwisko odbiorcy',
    )
    recipient_phone = models.CharField(
        max_length=32,
        verbose_name='Telefon odbiorcy',
    )
    recipient_email = models.EmailField(
        blank=True,
        verbose_name='E-mail odbiorcy',
    )
    recipient_postal_code = models.CharField(
        max_length=10,
        verbose_name='Kod pocztowy odbiorcy',
    )
    recipient_address = models.CharField(
        max_length=255,
        verbose_name='Adres (ulica, nr domu, nr mieszkania)',
    )
    recipient_city = models.CharField(
        max_length=100,
        verbose_name='Miasto odbiorcy',
    )

    parcel_locker_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Numer paczkomatu',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Wysyłka'
        verbose_name_plural = 'Wysyłki'
        ordering = ['-created_at']

    def __str__(self):
        label = self.tracking_number or f'#{self.pk}'
        return f'{self.get_carrier_display()} - {label}'
