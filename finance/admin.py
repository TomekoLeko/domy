from django.contrib import admin
from .models import Payment, SettlementAllocation


class SettlementAllocationInline(admin.TabularInline):
    model = SettlementAllocation
    extra = 0


@admin.register(SettlementAllocation)
class SettlementAllocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment', 'order_item', 'allocated_amount')
    list_filter = ('payment__payment_type',)
    raw_id_fields = ('payment', 'order_item')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    inlines = (SettlementAllocationInline,)
    list_display = ('created_at', 'payment_type', 'payment_method', 'amount', 'related_user', 'created_by')
    list_filter = ('payment_type', 'payment_method', 'created_at')
    search_fields = ('description', 'related_user__username', 'created_by__username')
    readonly_fields = ('created_at', 'created_by')
