"""Opłata usługowa za zamówienia poniżej progu wartości towaru."""

from decimal import Decimal

from .models import Order, OrderItem, Product

LOW_ORDER_SERVICE_THRESHOLD = Decimal('200.00')
LOW_ORDER_SERVICE_GROSS_PRICE = Decimal('15.00')


def maybe_append_low_order_service_item(order):
    """
    Gdy wartość towaru w zamówieniu (order.total_cost w momencie wywołania) jest < 200 zł,
    dopina pierwszy aktywny produkt typu wysyłka (`type=shipment`) jako pozycję po 15 zł brutto.

    Aktualizuje `total_cost` i `max_payable_amount` (jeśli ustawione). Nie tworzy redukcji magazynowej.
    Zwraca utworzony OrderItem lub None.
    """
    merchandise_total = order.total_cost
    if merchandise_total >= LOW_ORDER_SERVICE_THRESHOLD:
        return None

    service_product = (
        Product.objects.filter(type=Product.TYPE_SHIPMENT, is_active=True).order_by('pk').first()
    )
    if service_product is None:
        return None

    item = OrderItem.objects.create(
        order=order,
        product=service_product,
        price=LOW_ORDER_SERVICE_GROSS_PRICE,
        buyer_id=order.buyer_id,
    )

    order.total_cost = merchandise_total + LOW_ORDER_SERVICE_GROSS_PRICE
    update_fields = ['total_cost']
    if order.max_payable_amount is not None:
        order.max_payable_amount = order.max_payable_amount + LOW_ORDER_SERVICE_GROSS_PRICE
        update_fields.append('max_payable_amount')
    order.save(update_fields=update_fields)

    return item
