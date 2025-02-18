from django.db import models
from django.conf import settings
from decimal import Decimal

class Payment(models.Model):
    PAYMENT_TYPES = [
        ('contribution', 'Wpłata od wspierającego'),
        ('order', 'Płatność za zamówienie'),
        ('beneficiary', 'Zamówienie beneficjenta'),
        ('refund', 'Zwrot środków'),
        ('expense', 'Wydatek'),
        ('other', 'Inne'),
        ('invoice', 'Faktura'),
    ]

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Kwota"
    )
    payment_type = models.CharField(
        max_length=30,
        choices=PAYMENT_TYPES,
        verbose_name="Typ płatności"
    )
    description = models.TextField(
        verbose_name="Opis"
    )
    related_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_payments',
        verbose_name="Powiązany użytkownik"
    )
    related_order = models.ForeignKey(
        'products.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Powiązane zamówienie"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_payments',
        verbose_name="Utworzone przez"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data utworzenia"
    )
    payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data płatności"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Płatność"
        verbose_name_plural = "Płatności"

    def __str__(self):
        return f"{self.get_payment_type_display()}: {self.amount} zł"
