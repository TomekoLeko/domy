from django.db import models
from django.conf import settings
from decimal import Decimal
from stock.models import Supplier
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from users.models import Profile
from products.models import OrderItem
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce

class Payment(models.Model):
    PAYMENT_TYPES = [
        ('contribution', 'Wpłata od wspierającego'),
        ('order', 'Płatność za zamówienie'),
        ('refund', 'Zwrot środków'),
        ('expense', 'Wydatek'),
        ('other', 'Inne'),
        ('invoice', 'Faktura'),
    ]

    # Kanał / instrument zapłaty (osobno od payment_type — kategoria biznesowa).
    PAYMENT_METHOD_CHOICES = [
        ('transfer', 'Przelew'),
        ('cash', 'Gotówka'),
        ('cod', 'Pobranie'),
        ('card', 'Karta'),
        ('blik', 'BLIK'),
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
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='transfer',
        verbose_name="Sposób zapłaty",
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
    related_order_items = models.ManyToManyField(
        'products.OrderItem',
        blank=True,
        related_name='payments',
        verbose_name="Powiązane elementy zamówienia"
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

    @property
    def available_amount(self):
        used_amount = sum(item.price for item in self.related_order_items.all())
        return self.amount - used_amount

    @classmethod
    def get_available_contributions(cls):
        available_contributions = cls.objects.filter(
            payment_type='contribution'
        ).annotate(
            used_amount=Coalesce(Sum('related_order_items__price'), 0, output_field=DecimalField(max_digits=10, decimal_places=2))
        ).filter(
            amount__gt=F('used_amount')
        ).order_by('payment_date')
        return available_contributions

    @classmethod
    def get_available_contributions_amount(cls):
        available_contributions = cls.get_available_contributions()
        return sum(contribution.available_amount for contribution in available_contributions)


class SettlementAllocation(models.Model):
    """
    Jawny podział kwoty płatności na pozycje zamówienia (docelowo zamiast wyłącznie M2M
    related_order_items + heurystyki w kodzie).
    """

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='settlement_allocations',
        verbose_name='Płatność',
    )
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='settlement_allocations',
        verbose_name='Pozycja zamówienia',
    )
    allocated_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Kwota przypisana do pozycji',
    )

    class Meta:
        verbose_name = 'Alokacja rozliczenia'
        verbose_name_plural = 'Alokacje rozliczeń'
        constraints = [
            models.UniqueConstraint(
                fields=['payment', 'order_item'],
                name='finance_settlementallocation_payment_orderitem_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['payment']),
            models.Index(fields=['order_item']),
        ]

    def __str__(self):
        return f'{self.payment_id} → item {self.order_item_id}: {self.allocated_amount} zł'


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='invoices')
    net_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
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

class MonthlyContributionUsage(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='monthly_usage')
    year = models.IntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    limit = models.IntegerField()
    discount_rate_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    order_items = models.ManyToManyField(OrderItem, related_name='monthly_usage', blank=True)

    class Meta:
        unique_together = ['profile', 'year', 'month']
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.profile.user.username} - {self.year}/{self.month}"

    def clean(self):
        # Skip validation if this is a new instance (not saved yet)
        if self.pk is None:
            return
            
        # Calculate total usage from related order items
        total_usage = sum(item.price for item in self.order_items.all())

        if total_usage > self.limit:
            raise ValidationError(
                f"Total usage ({total_usage}) exceeds the monthly limit ({self.limit})"
            )

    def save(self, *args, **kwargs):
        # Only run clean() if the instance already exists
        if self.pk is not None:
            self.clean()
        super().save(*args, **kwargs)

    @property
    def total_usage(self):
        return sum(item.price for item in self.order_items.all())

    @property
    def remaining_limit(self):
        return self.limit - self.total_usage
