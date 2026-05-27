"""Pozycja wysyłki dopinana automatycznie do każdego zamówienia."""

from decimal import Decimal

from .models import Order, OrderItem, Product

ORDER_SHIPMENT_THRESHOLD = Decimal('200.00')
ORDER_SHIPMENT_PRICE_BELOW_THRESHOLD = Decimal('15.00')
ORDER_SHIPMENT_PRICE_AT_OR_ABOVE_THRESHOLD = Decimal('0.00')


def append_shipment_order_item(order):
    """
    Dopina pierwszy aktywny produkt typu wysyłka (`type=shipment`) do zamówienia.

    Cena brutto: 15 zł gdy wartość towaru (order.total_cost w momencie wywołania) < 200 zł,
    w przeciwnym razie 0 zł.

    Aktualizuje `total_cost` i `max_payable_amount` (jeśli ustawione). Nie tworzy redukcji magazynowej.
    Zwraca utworzony OrderItem lub None, gdy brak aktywnego produktu wysyłki.
    """
    merchandise_total = order.total_cost
    if merchandise_total >= ORDER_SHIPMENT_THRESHOLD:
        shipment_price = ORDER_SHIPMENT_PRICE_AT_OR_ABOVE_THRESHOLD
    else:
        shipment_price = ORDER_SHIPMENT_PRICE_BELOW_THRESHOLD

    service_product = (
        Product.objects.filter(type=Product.TYPE_SHIPMENT, is_active=True).order_by('pk').first()
    )
    if service_product is None:
        return None

    item = OrderItem.objects.create(
        order=order,
        product=service_product,
        price=shipment_price,
        buyer_id=order.buyer_id,
    )

    order.total_cost = merchandise_total + shipment_price
    update_fields = ['total_cost']
    if order.max_payable_amount is not None:
        order.max_payable_amount = order.max_payable_amount + shipment_price
        update_fields.append('max_payable_amount')
    order.save(update_fields=update_fields)

    return item


# Zachowana nazwa dla istniejących importów.
maybe_append_low_order_service_item = append_shipment_order_item
