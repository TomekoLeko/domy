from django.db import models
from products.models import Product
from products.models import Order

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

class SupplyOrder(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='supply_orders')
    invoice = models.ForeignKey('finance.Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='supply_orders')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Supply Order {self.id} - {self.supplier.name}"

    class Meta:
        ordering = ['-created_at']

class StockEntry(models.Model):
    STOCK_TYPE_CHOICES = [
        ('physical', 'Physical'),
        ('virtual', 'Virtual'),
    ]

    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='stock_entries')
    supply_order = models.ForeignKey(SupplyOrder, on_delete=models.PROTECT, related_name='stock_entries')
    quantity = models.PositiveIntegerField()
    net_cost = models.DecimalField(max_digits=10, decimal_places=2)
    gross_cost = models.DecimalField(max_digits=10, decimal_places=2)
    stock_type = models.CharField(max_length=10, choices=STOCK_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    remaining_quantity = models.PositiveIntegerField()  # Track remaining stock

    def __str__(self):
        return f"{self.product.name} - {self.quantity} units ({self.stock_type})"

    def save(self, *args, **kwargs):
        if not self.id:  # Only set remaining_quantity on creation
            self.remaining_quantity = self.quantity
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['created_at']  # Oldest first for FIFO

class StockReduction(models.Model):
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, related_name='stock_reductions')
    order = models.ForeignKey('products.Order', on_delete=models.PROTECT, related_name='stock_reductions')
    quantity = models.PositiveIntegerField()
    stock_entry = models.ForeignKey(StockEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='reductions')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reduction: {self.product.name} - {self.quantity} units"

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
                    # for the remaining quantity
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
                        quantity=remaining_quantity
                    )
                    # The new reduction will handle its own stock assignment in its save method
        
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at'] 
