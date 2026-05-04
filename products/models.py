from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from decimal import Decimal


def payment_amount_attributed_to_order_item(payment, order_item):
    """
    Kwota płatności liczona dla danej pozycji zamówienia, gdy jedna płatność
    jest powiązana M2M z wieloma pozycjami: proporcjonalnie wg ceny pozycji
    względem sumy cen powiązanych pozycji (raty / jedna wpłata na całe zamówienie).
    """
    linked = list(payment.related_order_items.all())
    ids = {x.id for x in linked}
    if order_item.id not in ids:
        return Decimal('0')
    denom = sum((x.price for x in linked), start=Decimal('0'))
    if denom <= 0:
        return Decimal('0')
    return payment.amount * order_item.price / denom


class ProductCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kategoria produktu"
        verbose_name_plural = "Kategorie produktów"

class Product(models.Model):
    UNIT_CHOICES = [
        ("l", "Litry"),
        ("kg", "Kilogramy"),
        ("pcs", "Sztuki"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    categories = models.ManyToManyField(ProductCategory, related_name='products', blank=True)
    vat = models.DecimalField(max_digits=4, decimal_places=2, default=23.00)
    ean = models.CharField(max_length=13, blank=True, null=True)
    volume_value = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=1.00
    )
    volume_unit = models.CharField(
        max_length=10, 
        choices=UNIT_CHOICES,
        default='pcs'
    )

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='', blank=True, null=True)
    caption = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Image for {self.product.name}"

class PriceList(models.Model):
    name = models.CharField(max_length=255)
    is_standard = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # If this price list is being set as standard, unset any other standard price list
        if self.is_standard:
            PriceList.objects.filter(is_standard=True).update(is_standard=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Price(models.Model):
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name='prices')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='prices')
    net_price = models.DecimalField(max_digits=10, decimal_places=2)
    gross_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['price_list', 'product'], name='unique_price_per_product_per_list')
        ]

    def __str__(self):
        return f"{self.product.name} ({self.price_list.name}) - Net: {self.net_price}, Gross: {self.gross_price}"

class Cart(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    buyer = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='shopping_carts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.buyer.profile.name or self.buyer.username}"

    @property
    def total_cost(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_items(self):
        return self.items.count()

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Store the price at the time of adding to cart
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cart_items',
        verbose_name="Przypisany odbiorca"
    )

    @property
    def subtotal(self):
        return self.quantity * self.price

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Oczekujące'),
        ('accepted', 'Przyjęte'),
        ('shipped', 'Nadane'),
        ('delivered', 'Dostarczone'),
        ('cancelled', 'Anulowane'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Oczekujące na rozliczenie'),
        ('processing', 'W trakcie rozliczenia'),
        ('partial', 'Częściowo opłacone'),
        ('paid', 'Opłacone'),
        ('rejected', 'Odrzucone'),
        ('cancelled', 'Rozliczenie anulowane'),
    ]

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    buyer = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='buyer_orders')
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        verbose_name='Status rozliczenia',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    max_payable_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Order {self.id} by {self.buyer.profile.name or self.buyer.username}"

    def update_payment_status_from_settlement(self):
        """
        Ustawia payment_status na podstawie rozliczenia pozycji kupującego (`buyer_id == order.buyer_id`).

        Sumuje `OrderItem.left_to_pay` i `price` — `left_to_pay` liczy się z `SettlementAllocation`
        oraz przejściowo z podziału proporcjonalnego M2M tam, gdzie brak wiersza alokacji.

        Nie nadpisuje stanów końcowych ustawianych ręcznie: rejected, cancelled.
        """
        if self.payment_status in ('rejected', 'cancelled'):
            return

        buyer_id = self.buyer_id
        items = [it for it in self.items.all() if it.buyer_id == buyer_id]
        if not items:
            return

        total_left = sum((item.left_to_pay for item in items), start=Decimal('0'))
        total_price = sum((item.price for item in items), start=Decimal('0'))
        paid_amount = total_price - total_left

        if total_left <= Decimal('0.01'):
            new_status = 'paid'
        elif paid_amount > Decimal('0.01'):
            new_status = 'partial'
        else:
            new_status = 'pending'

        if self.payment_status != new_status:
            self.payment_status = new_status
            self.save(update_fields=['payment_status'])

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at the time of order
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_order_items',
        verbose_name="Przypisany odbiorca"
    )

    @property
    def sum_of_order_item_payments(self):
        """
        Settled amount on this line: use SettlementAllocation.allocated_amount when present
        for a linked payment; otherwise legacy proportional split from M2M. Includes
        allocations whose payment is not in related_order_items (orphan rows).
        """
        alloc_by_payment = {}
        allocations = self.settlement_allocations.all()
        if 'settlement_allocations' not in getattr(self, '_prefetched_objects_cache', {}):
            allocations = self.settlement_allocations.all()
        for sa in allocations:
            alloc_by_payment[sa.payment_id] = sa.allocated_amount

        payments_qs = self.payments.all()
        if 'payments' not in getattr(self, '_prefetched_objects_cache', {}):
            payments_qs = self.payments.prefetch_related(
                'related_order_items',
                'settlement_allocations',
            ).all()

        linked_payment_ids = set()
        total = Decimal('0')
        for p in payments_qs:
            linked_payment_ids.add(p.id)
            if p.id in alloc_by_payment:
                total += alloc_by_payment[p.id]
            else:
                total += payment_amount_attributed_to_order_item(p, self)

        for payment_id, amount in alloc_by_payment.items():
            if payment_id not in linked_payment_ids:
                total += amount

        return total

    @property
    def left_to_pay(self):
        raw = self.price - self.sum_of_order_item_payments
        if raw <= Decimal('0.01'):
            return Decimal('0.00')
        return raw.quantize(Decimal('0.01'))

