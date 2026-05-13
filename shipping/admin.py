from django.contrib import admin

from .models import Shipment


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'carrier',
        'delivery_method',
        'tracking_number',
        'recipient_name',
        'recipient_city',
        'created_at',
    )
    list_filter = ('carrier', 'delivery_method', 'created_at')
    search_fields = (
        'tracking_number',
        'recipient_name',
        'recipient_phone',
        'recipient_email',
        'recipient_postal_code',
        'recipient_city',
        'parcel_locker_code',
    )
    readonly_fields = ('created_at',)
