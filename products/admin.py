from django.contrib import admin
from .models import Product, ProductImage, PriceList, Order

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]

admin.site.register(PriceList)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'status', 'payment_status', 'total_cost', 'created_at')
    list_filter = ('status', 'payment_status', 'created_at')
    readonly_fields = ('created_at',)
