from django.db import models
from django.conf import settings
from decimal import Decimal
from stock.models import Supplier
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from users.models import Profile
from products.models import OrderItem
from django.db.models import Sum, F, Q, ExpressionWrapper, DecimalField
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

    def used_amount_settlement_and_legacy(self):
        """
        Kwota płatności już „przypięta”: suma SettlementAllocation.allocated_amount
        plus pełna cena pozycji tylko w M2M bez wiersza alokacji (faza przejściowa).
        """
        total_alloc = sum(
            (a.allocated_amount for a in self.settlement_allocations.all()),
            start=Decimal('0'),
        )
        item_ids_with_alloc = {a.order_item_id for a in self.settlement_allocations.all()}
        legacy = sum(
            (oi.price for oi in self.related_order_items.all() if oi.id not in item_ids_with_alloc),
            start=Decimal('0'),
        )
        return (total_alloc + legacy).quantize(Decimal('0.01'))

    @property
    def available_amount(self):
        return self.amount - self.used_amount_settlement_and_legacy()

    @classmethod
    def get_available_contributions(cls):
        """
        Kontrybucje z kwotą dostępną do dalszego przypisania (wg alokacji + legacy M2M).
        """
        candidates = cls.objects.filter(payment_type='contribution').prefetch_related(
            'settlement_allocations',
            'related_order_items',
        )
        eligible_ids = [
            p.pk
            for p in candidates
            if p.amount > p.used_amount_settlement_and_legacy()
        ]
        if not eligible_ids:
            return cls.objects.none()
        return (
            cls.objects.filter(pk__in=eligible_ids)
            .prefetch_related('settlement_allocations', 'related_order_items')
            .order_by('payment_date')
        )

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

    class Meta:
        unique_together = ['profile', 'year', 'month']
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.profile.user.username} - {self.year}/{self.month}"

    def donor_contribution_allocations_qs(self):
        """
        Contribution allocations on donor-paid lines for this beneficiary's orders,
        attributed to this calendar month via payment_date (or created_at if no date).
        """
        return SettlementAllocation.objects.filter(
            payment__payment_type='contribution',
            order_item__order__buyer_id=self.profile.user_id,
        ).exclude(
            order_item__buyer_id=F('order_item__order__buyer_id'),
        ).filter(
            Q(
                payment__payment_date__year=self.year,
                payment__payment_date__month=self.month,
            )
            | Q(
                payment__payment_date__isnull=True,
                payment__created_at__year=self.year,
                payment__created_at__month=self.month,
            ),
        )

    def distinct_order_item_ids_for_month(self):
        return list(
            self.donor_contribution_allocations_qs()
            .values_list('order_item_id', flat=True)
            .distinct()
        )

    def get_monthly_order_items(self):
        """Order lines counting toward this usage month (for API / templates)."""
        ids = self.distinct_order_item_ids_for_month()
        if not ids:
            return OrderItem.objects.none()
        return (
            OrderItem.objects.filter(id__in=ids)
            .select_related('product', 'buyer', 'order')
            .order_by('order_id', 'id')
        )

    @property
    def monthly_order_items(self):
        """Alias for templates (`{% for oi in usage.monthly_order_items %}`)."""
        return self.get_monthly_order_items()

    def clean(self):
        if self.pk is None:
            return

        total_usage = self.total_usage
        if total_usage > Decimal(self.limit):
            raise ValidationError(
                f"Total usage ({total_usage}) exceeds the monthly limit ({self.limit})"
            )

    def save(self, *args, **kwargs):
        if self.pk is not None:
            self.clean()
        super().save(*args, **kwargs)

    @property
    def total_usage(self):
        ids = self.distinct_order_item_ids_for_month()
        if not ids:
            return Decimal('0.00')
        agg = OrderItem.objects.filter(id__in=ids).aggregate(s=Sum('price'))
        val = agg['s'] or Decimal('0')
        return val.quantize(Decimal('0.01'))

    @property
    def remaining_limit(self):
        return (Decimal(self.limit) - self.total_usage).quantize(Decimal('0.01'))
