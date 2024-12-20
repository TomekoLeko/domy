from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="product_images/", blank=True, null=True)
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

