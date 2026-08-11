from django.db import models
from products.models import Product, Order
from datetime import datetime
from django.utils import timezone

class Supplier(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    postal = models.CharField(max_length=10)
    city = models.CharField(max_length=100)
    mail = models.EmailField()
    phone = models.CharField(max_length=20)
    nip = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Dostawca"
        verbose_name_plural = "Dostawcy"


class Vacation(models.Model):
    """Urlop — okres niedostępności do realizacji zamówień."""

    start_date = models.DateField(verbose_name='Data od')
    end_date = models.DateField(verbose_name='Data do')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'Data zakończenia nie może być wcześniejsza niż data rozpoczęcia.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Urlop {self.start_date} – {self.end_date}"

    class Meta:
        ordering = ['start_date']
        verbose_name = 'Urlop'
        verbose_name_plural = 'Urlopy'

class SupplyOrder(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='supply_orders')
    invoice = models.ForeignKey('finance.Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='supply_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    order_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Get current date
            now = datetime.now()
            month = now.month
            year = now.year

            # Get the last order from the current month
            last_order = SupplyOrder.objects.filter(
                created_at__month=month,
                created_at__year=year
            ).order_by('-order_number').first()

            # Generate new number
            if last_order and last_order.order_number:
                # Extract the number from the last order
                last_number = int(last_order.order_number.split('/')[0])
                new_number = str(last_number + 1).zfill(2)
            else:
                new_number = '01'

            # Create the order number
            self.order_number = f"{new_number}/{str(month).zfill(2)}/{year}"

        super().save(*args, **kwargs)

    def get_total_net_cost(self):
        return sum(entry.total_net_cost for entry in self.stock_entries.all())

    def get_total_gross_cost(self):
        return sum(entry.total_gross_cost for entry in self.stock_entries.all())

    def __str__(self):
        return f"Zamówienie {self.order_number} - {self.supplier.name}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Zamówienie od dostawcy"
        verbose_name_plural = "Zamówienia od dostawców"

class StockEntry(models.Model):
    STOCK_TYPE_CHOICES = [
        ('physical', 'Fizyczny'),
        ('virtual', 'Wirtualny'),
    ]

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_entries')
    supply_order = models.ForeignKey(SupplyOrder, on_delete=models.PROTECT, related_name='stock_entries')
    quantity = models.PositiveIntegerField()
    net_cost = models.DecimalField(max_digits=10, decimal_places=2)
    gross_cost = models.DecimalField(max_digits=10, decimal_places=2)
    receiving_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Koszt obsługi przyjęcia',
    )
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    stock_type = models.CharField(max_length=10, choices=STOCK_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    remaining_quantity = models.PositiveIntegerField()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:  # Only on creation
            # Copy VAT rate from product if available
            if hasattr(self.product, 'vat_rate'):
                self.vat_rate = self.product.vat_rate
            # Set remaining_quantity
            self.remaining_quantity = self.quantity
        super().save(*args, **kwargs)
        if is_new:
            self._assign_pending_stock_reductions()

    def _assign_pending_stock_reductions(self):
        """
        Gdy pozycje zamówień zostały utworzone zanim towar pojawił się w magazynie,
        `StockReduction.stock_entry` może pozostać puste. Po dodaniu nowego `StockEntry`
        przypisujemy FIFO brakujące `StockEntry` do takich pending redukcji.
        """
        pending_reductions = (
            StockReduction.objects.filter(product=self.product, stock_entry__isnull=True)
            .order_by('created_at', 'id')
        )

        # Ustawiamy redukcje po kolei, żeby wcześniejsze redukcje “zjadały” zapas pierwsze (FIFO).
        for reduction in pending_reductions:
            # Jeśli w międzyczasie ktoś przypisał stock_entry — pomijamy.
            if reduction.stock_entry_id is not None:
                continue
            reduction.save()

    def __str__(self):
        return f"{self.product.name} - {self.quantity} szt. ({self.get_stock_type_display()})"

    @property
    def total_net_cost(self):
        return self.quantity * self.net_cost

    @property
    def total_gross_cost(self):
        return self.quantity * self.gross_cost

    class Meta:
        ordering = ['created_at']  # Oldest first for FIFO
        verbose_name = "Przyjęcie towaru"
        verbose_name_plural = "Przyjęcia towaru"

class StockReduction(models.Model):
    STOCK_TYPE_CHOICES = [
        ('physical', 'Fizyczny'),
        ('virtual', 'Wirtualny'),
    ]

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='stock_reductions')
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='stock_reductions')
    order_item = models.ForeignKey('products.OrderItem', on_delete=models.PROTECT, related_name='stock_reductions', null=True, blank=True)
    quantity = models.PositiveIntegerField()
    stock_entry = models.ForeignKey(StockEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='reductions')
    stock_type = models.CharField(max_length=10, choices=STOCK_TYPE_CHOICES, default='physical')
    issuing_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Koszt obsługi wydania',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Wydanie: {self.product.name} - {self.quantity} szt."

    def save(self, *args, **kwargs):
        if not self.stock_entry and self.product:
            # Auto-assign stock entry using FIFO if not manually specified
            available_entry = (StockEntry.objects
                             .filter(product=self.product, remaining_quantity__gt=0)
                             .order_by('created_at')
                             .first())
            
            if available_entry:
                if available_entry.remaining_quantity >= self.quantity:
                    # If we have enough quantity in this entry, use it
                    self.stock_entry = available_entry
                    available_entry.remaining_quantity -= self.quantity
                    available_entry.save()
                else:
                    # If we don't have enough, take what we can and create a new reduction
                    remaining_quantity = self.quantity - available_entry.remaining_quantity
                    
                    # Update current reduction to use all remaining stock from this entry
                    self.quantity = available_entry.remaining_quantity
                    self.stock_entry = available_entry
                    available_entry.remaining_quantity = 0
                    available_entry.save()
                    
                    # Create new reduction for remaining quantity
                    new_reduction = StockReduction.objects.create(
                        product=self.product,
                        order=self.order,
                        order_item=self.order_item,
                        stock_type=self.stock_type,
                        quantity=remaining_quantity
                    )
        
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Wydanie towaru"
        verbose_name_plural = "Wydania towaru" 
