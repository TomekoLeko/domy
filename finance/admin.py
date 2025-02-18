from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'payment_type', 'amount', 'related_user', 'created_by')
    list_filter = ('payment_type', 'created_at')
    search_fields = ('description', 'related_user__username', 'created_by__username')
    readonly_fields = ('created_at', 'created_by')
