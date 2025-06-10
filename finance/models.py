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
        used_amount = sum(item.subtotal for item in self.related_order_items.all())
        return self.amount - used_amount

    @classmethod
    def get_available_contributions(cls):
        available_contributions = cls.objects.filter(
            payment_type='contribution'
        ).annotate(
            used_amount=Coalesce(Sum('related_order_items__subtotal'), 0, output_field=DecimalField(max_digits=10, decimal_places=2))
        ).filter(
            amount__gt=F('used_amount')
        ).order_by('payment_date')
        return available_contributions

    @classmethod
    def get_available_contributions_amount(cls):
        available_contributions = cls.get_available_contributions()
        return sum(contribution.available_amount for contribution in available_contributions)

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
        total_usage = sum(item.quantity * item.price for item in self.order_items.all())
        
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
        return sum(item.quantity * item.price for item in self.order_items.all())

    @property
    def remaining_limit(self):
        return self.limit - self.total_usage

class PaymentAllocation(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name="Płatność"
    )
    order_item = models.ForeignKey(
        'products.OrderItem',
        on_delete=models.CASCADE,
        related_name='payment_allocations',
        verbose_name="Element zamówienia"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Kwota alokacji"
    )
    allocation_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data alokacji"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data utworzenia"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Data aktualizacji"
    )

    class Meta:
        verbose_name = "Alokacja płatności"
        verbose_name_plural = "Alokacje płatności"
        ordering = ['-allocation_date']

    def __str__(self):
        return f"Alokacja {self.amount} zł z płatności {self.payment.id} do elementu zamówienia {self.order_item.id}"

    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Check if allocation amount is positive
        if self.amount <= 0:
            raise ValidationError("Kwota alokacji musi być większa od 0")
            
        # Check if allocation amount doesn't exceed payment's available amount
        payment_allocated = self.payment.allocations.exclude(id=self.id).aggregate(
            total=models.Sum('amount'))['total'] or 0
        if (payment_allocated + self.amount) > self.payment.amount:
            raise ValidationError("Suma alokacji nie może przekraczać kwoty płatności")
            
        # Check if allocation amount doesn't exceed order item's remaining amount
        item_allocated = self.order_item.payment_allocations.exclude(id=self.id).aggregate(
            total=models.Sum('amount'))['total'] or 0
        if (item_allocated + self.amount) > self.order_item.subtotal:
            raise ValidationError("Suma alokacji nie może przekraczać kwoty elementu zamówienia")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
