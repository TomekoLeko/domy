from django.db import models
from django.conf import settings
from decimal import Decimal
from stock.models import Supplier

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
    sender = models.TextField(
        verbose_name="Nadawca",
        blank=True,
        null=True
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

class Invoice(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='invoices')
    net_price = models.DecimalField(max_digits=10, decimal_places=2)
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2)
    gross_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Copied supplier details
    supplier_name = models.CharField(max_length=255)
    supplier_address = models.CharField(max_length=255)
    supplier_postal = models.CharField(max_length=10)
    supplier_city = models.CharField(max_length=100)
    supplier_nip = models.CharField(max_length=10)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Faktura {self.invoice_number} - {self.supplier_name}"

    def save(self, *args, **kwargs):
        # Copy supplier details before saving
        if self.supplier:
            self.supplier_name = self.supplier.name
            self.supplier_address = self.supplier.address
            self.supplier_postal = self.supplier.postal
            self.supplier_city = self.supplier.city
            self.supplier_nip = self.supplier.nip
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Faktura"
        verbose_name_plural = "Faktury"
