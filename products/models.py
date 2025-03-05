from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings

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

    @property
    def subtotal(self):
        return self.quantity * self.price

class Order(models.Model):
    STATUS_CHOICES = [
        ('accepted', 'Przyjęte'),
        ('shipped', 'Nadane'),
        ('delivered', 'Dostarczone'),
        ('cancelled', 'Anulowane'),
    ]

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    buyer = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='buyer_orders')
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='accepted'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Order {self.id} by {self.buyer.profile.name or self.buyer.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at the time of order
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.price
        super().save(*args, **kwargs)

