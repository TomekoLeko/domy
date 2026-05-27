"""API zestawienia finansowego zamówień (przychód i koszt zakupu)."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Prefetch
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from domy.decorators import require_authenticated_staff_or_superuser
from products.models import Order, OrderItem, Product
from stock.models import StockReduction

MONEY_QUANT = Decimal('0.01')
VIRTUAL_SHIPMENT_NAME = 'Wysyłka'


def _money_str(value):
    return str(value.quantize(MONEY_QUANT))


def _product_image_url(request, product):
    first_image = product.images.first()
    if first_image and first_image.image:
        return request.build_absolute_uri(first_image.image.url)
    return None


def _order_item_purchase_cost(order_item):
    """
    Koszt zakupu jednej pozycji OrderItem (zwykle 1 szt.) z powiązań StockReduction → StockEntry.
    Zwraca (koszt_jednostkowy, kompletne_pokrycie).
    """
    reductions = list(order_item.stock_reductions.all())
    if not reductions:
        return Decimal('0'), False

    covered_qty = 0
    total_cost = Decimal('0')
    for reduction in reductions:
        if reduction.stock_entry_id is None:
            return total_cost, False
        covered_qty += reduction.quantity
        total_cost += reduction.quantity * reduction.stock_entry.net_cost

    if covered_qty < 1:
        return total_cost, False
    return total_cost, True


def _linked_shipments_for_order(order_items):
    """
    Unikalne obiekty Shipment powiązane z pozycjami zamówienia (FK `OrderItem.shipment`).

    W module Wysyłki FK ustawiane jest na pozycjach towarowych (`TYPE_ITEM`), nie na
    pozycji opłaty za wysyłkę (`TYPE_SHIPMENT`).
    """
    by_id = {}
    for order_item in order_items:
        if order_item.shipment_id is None:
            continue
        if order_item.shipment_id not in by_id:
            by_id[order_item.shipment_id] = order_item.shipment
    return list(by_id.values())


def _shipment_line_payload(bucket):
    """Jedna zagregowana pozycja wysyłki dla osobnej tabeli w UI."""
    shipment_amount = bucket.get('shipment_amount', Decimal('0'))
    shipment_shipping_cost = bucket.get('shipment_shipping_cost', Decimal('0'))
    shipment_packaging_cost = bucket.get('shipment_packaging_cost', Decimal('0'))
    total_cost = shipment_shipping_cost + shipment_packaging_cost
    incomplete = bucket['has_incomplete_calculations']
    profit = shipment_amount - total_cost

    return {
        'product_name': bucket['product_name'],
        'linked_shipment_count': bucket.get('linked_shipment_count', 0),
        'is_virtual': bucket['is_virtual'],
        'quantity': bucket['quantity'],
        'price': _money_str(shipment_amount),
        'packaging_cost': _money_str(shipment_packaging_cost),
        'shipping_cost': _money_str(shipment_shipping_cost),
        'profit': None if incomplete else _money_str(profit),
        'has_incomplete_calculations': incomplete,
    }


def _aggregate_order_lines(request, order_items):
    """
    Grupuje pozycje towarowe i jedną linię wysyłki.
    Zwraca (linie_produktów, wysyłka, has_incomplete_calculations).

    Każda linia produktowa ma `has_incomplete_calculations`, gdy przynajmniej jedna
    `OrderItem` w wierszu ma niepełne pokrycie kosztu magazynowego.
    """
    item_buckets = defaultdict(
        lambda: {
            'product_id': None,
            'product_name': '',
            'image_url': None,
            'product_type': Product.TYPE_ITEM,
            'is_virtual': False,
            'quantity': 0,
            'unit_price': Decimal('0'),
            'unit_cost': Decimal('0'),
            'has_incomplete_calculations': False,
        }
    )
    shipment_bucket = {
        'product_id': None,
        'product_name': VIRTUAL_SHIPMENT_NAME,
        'image_url': None,
        'product_type': Product.TYPE_SHIPMENT,
        'is_virtual': False,
        'quantity': 0,
        'unit_price': Decimal('0'),
        'unit_cost': Decimal('0'),
        'has_incomplete_calculations': False,
        'shipment_amount': Decimal('0'),
        'shipment_shipping_cost': Decimal('0'),
        'shipment_packaging_cost': Decimal('0'),
    }
    has_incomplete = False
    has_shipment_line = False

    for order_item in order_items:
        product = order_item.product
        unit_price = order_item.price.quantize(MONEY_QUANT)

        if product.type == Product.TYPE_SHIPMENT:
            has_shipment_line = True
            shipment_bucket['quantity'] += 1
            shipment_bucket['shipment_amount'] += unit_price
            continue

        if product.type != Product.TYPE_ITEM:
            continue

        unit_cost, complete = _order_item_purchase_cost(order_item)
        unit_cost = unit_cost.quantize(MONEY_QUANT)
        if not complete:
            has_incomplete = True

        # Dla spójności z flagą — rozdzielamy też bucket po `complete`,
        # żeby wiersz odpowiadał konkretnemu statusowi pokrycia.
        key = (product.id, unit_price, unit_cost, complete)
        bucket = item_buckets[key]
        bucket['product_id'] = product.id
        bucket['product_name'] = product.name
        bucket['image_url'] = _product_image_url(request, product)
        bucket['product_type'] = Product.TYPE_ITEM
        bucket['unit_price'] = unit_price
        bucket['unit_cost'] = unit_cost
        bucket['has_incomplete_calculations'] = not complete
        bucket['quantity'] += 1

    def bucket_to_product_line(bucket):
        quantity = bucket['quantity']
        unit_price = bucket['unit_price']
        unit_cost = bucket['unit_cost']
        return {
            'product_id': bucket['product_id'],
            'product_name': bucket['product_name'],
            'image_url': bucket['image_url'],
            'product_type': bucket['product_type'],
            'quantity': quantity,
            'unit_price': _money_str(unit_price),
            'amount': _money_str(unit_price * quantity),
            'unit_cost': _money_str(unit_cost),
            'cost': _money_str(unit_cost * quantity),
            'has_incomplete_calculations': bucket['has_incomplete_calculations'],
        }

    product_lines = [bucket_to_product_line(b) for b in item_buckets.values()]
    product_lines.sort(key=lambda row: (row['product_name'] or '', row['unit_price']))

    linked_shipments = _linked_shipments_for_order(order_items)
    shipment_bucket['linked_shipment_count'] = len(linked_shipments)

    for shipment in linked_shipments:
        if shipment.shipping_cost is None or shipment.packaging_cost is None:
            shipment_bucket['has_incomplete_calculations'] = True
            has_incomplete = True
            continue
        shipment_bucket['shipment_shipping_cost'] += shipment.shipping_cost
        shipment_bucket['shipment_packaging_cost'] += shipment.packaging_cost

    if not has_shipment_line and not linked_shipments:
        shipment_bucket['is_virtual'] = True
        shipment_bucket['quantity'] = 1
    elif linked_shipments:
        has_shipment_line = True

    shipment = _shipment_line_payload(shipment_bucket)
    return product_lines, shipment, has_incomplete or shipment['has_incomplete_calculations']


def _order_items_prefetch():
    return Prefetch(
        'items',
        queryset=OrderItem.objects.select_related('product', 'shipment').prefetch_related(
            'product__images',
            Prefetch(
                'stock_reductions',
                queryset=StockReduction.objects.select_related('stock_entry'),
            ),
        ),
    )


@require_GET
@require_authenticated_staff_or_superuser
def api_list_order_summaries(request):
    """
    GET /api/finance/order-summaries/
    Zestawienie zamówień z zagregowanymi pozycjami (przychód i koszt zakupu).
    """
    orders = (
        Order.objects.select_related('buyer')
        .prefetch_related(_order_items_prefetch())
        .order_by('-created_at')
    )

    orders_payload = []
    for order in orders:
        order_items = list(order.items.all())
        total_amount = sum((item.price for item in order_items), start=Decimal('0'))
        product_lines, shipment, has_incomplete = _aggregate_order_lines(
            request, order_items
        )

        orders_payload.append(
            {
                'id': order.id,
                'created_at': order.created_at.isoformat(),
                'total_amount': _money_str(total_amount),
                'has_incomplete_calculations': has_incomplete,
                'lines': product_lines,
                'shipment': shipment,
            }
        )

    return JsonResponse(
        {'orders': orders_payload},
        json_dumps_params={'ensure_ascii': False},
    )
