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
    STANDARD = 'Standard'
    BENEFICIARIES = 'Beneficiaries'

    PRICE_LIST_CHOICES = [
        (STANDARD, 'Standard'),
        (BENEFICIARIES, 'Beneficiaries'),
    ]

    name = models.CharField(max_length=50, choices=PRICE_LIST_CHOICES, default=STANDARD)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_lists')
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.get_name_display()} - {self.product.name}: {self.price}"
