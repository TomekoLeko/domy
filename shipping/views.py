import json

from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from domy.decorators import require_authenticated_staff_or_superuser
from products.models import OrderItem

from .models import Carrier, DeliveryMethod, Shipment


REQUIRED_SHIPMENT_FIELDS = (
    'recipient_name',
    'recipient_phone',
    'recipient_postal_code',
    'recipient_address',
    'recipient_city',
)

OPTIONAL_SHIPMENT_FIELDS = (
    'tracking_number',
    'notes',
    'recipient_email',
    'parcel_locker_code',
)


def _shipment_to_dict(shipment):
    return {
        'id': shipment.id,
        'carrier': shipment.carrier,
        'carrier_display': shipment.get_carrier_display(),
        'delivery_method': shipment.delivery_method,
        'delivery_method_display': shipment.get_delivery_method_display(),
        'tracking_number': shipment.tracking_number,
        'notes': shipment.notes,
        'recipient_name': shipment.recipient_name,
        'recipient_phone': shipment.recipient_phone,
        'recipient_email': shipment.recipient_email,
        'recipient_postal_code': shipment.recipient_postal_code,
        'recipient_address': shipment.recipient_address,
        'recipient_city': shipment.recipient_city,
        'parcel_locker_code': shipment.parcel_locker_code,
        'created_at': shipment.created_at.isoformat() if shipment.created_at else None,
    }


def _parse_shipment_payload(data):
    carrier = (data.get('carrier') or '').strip()
    if carrier not in Carrier.values:
        return None, JsonResponse({'detail': 'Invalid carrier'}, status=400)

    delivery_method = (data.get('delivery_method') or '').strip()
    if delivery_method not in DeliveryMethod.values:
        return None, JsonResponse({'detail': 'Invalid delivery_method'}, status=400)

    payload = {
        'carrier': carrier,
        'delivery_method': delivery_method,
    }
    for field in REQUIRED_SHIPMENT_FIELDS:
        value = (data.get(field) or '').strip()
        if not value:
            return None, JsonResponse({'detail': f'{field} is required'}, status=400)
        payload[field] = value

    for field in OPTIONAL_SHIPMENT_FIELDS:
        payload[field] = (data.get(field) or '').strip()

    return payload, None


@require_POST
@require_authenticated_staff_or_superuser
def api_create_shipment(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    payload, error_response = _parse_shipment_payload(data)
    if error_response is not None:
        return error_response

    shipment = Shipment.objects.create(**payload)

    return JsonResponse(
        {'status': 'success', 'shipment': _shipment_to_dict(shipment)},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_update_shipment(request, shipment_id):
    shipment = get_object_or_404(Shipment, id=shipment_id)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    payload, error_response = _parse_shipment_payload(data)
    if error_response is not None:
        return error_response

    for field, value in payload.items():
        setattr(shipment, field, value)
    shipment.save()

    return JsonResponse(
        {'status': 'success', 'shipment': _shipment_to_dict(shipment)},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_delete_shipment(request, shipment_id):
    shipment = get_object_or_404(Shipment, id=shipment_id)
    shipment.delete()
    return JsonResponse({'status': 'success', 'shipment_id': shipment_id})


@require_GET
@require_authenticated_staff_or_superuser
def api_list_unassigned_shipments(request):
    shipments = (
        Shipment.objects
        .filter(items__isnull=True)
        .order_by('-created_at')
    )
    return JsonResponse(
        {'shipments': [_shipment_to_dict(shipment) for shipment in shipments]},
        json_dumps_params={'ensure_ascii': False},
    )


def _order_item_to_dict(item, request):
    """Reprezentacja `OrderItem` dla listy w widoku administracyjnym wysyłek.

    Kontrakt celowo zbliżony do tego z `products.views.api_list_of_orders_for_admin`,
    żeby frontend mógł grupować pozycje tymi samymi helperami co na stronie Zamówień.
    """
    first_image = item.product.images.first() if item.product_id else None
    image_url = (
        request.build_absolute_uri(first_image.image.url)
        if first_image and first_image.image
        else None
    )

    buyer_label = None
    if item.buyer_id:
        buyer_label = (
            item.buyer.get_organization_name_or_full_name()
            or item.buyer.username
        )

    return {
        'id': item.id,
        'order_id': item.order_id,
        'product_id': item.product_id,
        'product_name': item.product.name if item.product_id else '',
        'image_url': image_url,
        'price': str(item.price),
        'buyer_id': item.buyer_id,
        'buyer_name': buyer_label,
    }


@require_GET
@require_authenticated_staff_or_superuser
def api_list_all_shipments(request):
    """Lista wszystkich wysyłek wraz z przypisanymi pozycjami zamówień.

    Frontend dzieli wyniki na sekcje "Do przypisania" (pozycje puste) oraz "Przypisane".
    """
    items_qs = OrderItem.objects.select_related('buyer', 'product').prefetch_related(
        'product__images'
    )
    shipments = (
        Shipment.objects
        .prefetch_related(Prefetch('items', queryset=items_qs))
        .order_by('-created_at')
    )

    shipments_data = []
    for shipment in shipments:
        shipment_dict = _shipment_to_dict(shipment)
        shipment_dict['items'] = [
            _order_item_to_dict(item, request) for item in shipment.items.all()
        ]
        shipments_data.append(shipment_dict)

    return JsonResponse(
        {'shipments': shipments_data},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_assign_order_items_to_shipments(request):
    """Przypisuje pozycje zamówienia do wysyłek na podstawie mapowania z frontendu.

    Oczekiwany payload:
        {
            "assignments": [
                {"shipment_id": 1, "order_item_ids": [10, 11]},
                {"shipment_id": 2, "order_item_ids": [12]}
            ]
        }

    Każda pozycja w `order_item_ids` dostaje ustawione FK `shipment`.
    Operacja jest atomowa - albo zapisujemy wszystkie przypisania, albo żadnego.
    """
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    raw_assignments = data.get('assignments')
    if not isinstance(raw_assignments, list):
        return JsonResponse({'detail': 'assignments must be a list'}, status=400)

    # Walidacja kształtu wejścia + zebranie identyfikatorów do jednej walidacji DB.
    shipment_ids = set()
    order_item_ids = set()
    normalized = []
    for entry in raw_assignments:
        if not isinstance(entry, dict):
            return JsonResponse({'detail': 'assignment must be an object'}, status=400)
        shipment_id = entry.get('shipment_id')
        items = entry.get('order_item_ids')
        if not isinstance(shipment_id, int) or shipment_id <= 0:
            return JsonResponse({'detail': 'Invalid shipment_id'}, status=400)
        if not isinstance(items, list) or not items:
            return JsonResponse(
                {'detail': 'order_item_ids must be a non-empty list'}, status=400
            )

        item_ids = []
        for item_id in items:
            if not isinstance(item_id, int) or item_id <= 0:
                return JsonResponse({'detail': 'Invalid order_item_id'}, status=400)
            if item_id in order_item_ids:
                return JsonResponse(
                    {'detail': f'Order item {item_id} assigned more than once'},
                    status=400,
                )
            order_item_ids.add(item_id)
            item_ids.append(item_id)

        shipment_ids.add(shipment_id)
        normalized.append({'shipment_id': shipment_id, 'order_item_ids': item_ids})

    if not normalized:
        return JsonResponse({'status': 'success', 'updated': 0})

    existing_shipment_ids = set(
        Shipment.objects.filter(id__in=shipment_ids).values_list('id', flat=True)
    )
    missing_shipments = shipment_ids - existing_shipment_ids
    if missing_shipments:
        return JsonResponse(
            {'detail': f'Shipments not found: {sorted(missing_shipments)}'},
            status=404,
        )

    existing_item_ids = set(
        OrderItem.objects.filter(id__in=order_item_ids).values_list('id', flat=True)
    )
    missing_items = order_item_ids - existing_item_ids
    if missing_items:
        return JsonResponse(
            {'detail': f'Order items not found: {sorted(missing_items)}'},
            status=404,
        )

    updated_total = 0
    with transaction.atomic():
        for entry in normalized:
            updated_total += OrderItem.objects.filter(
                id__in=entry['order_item_ids']
            ).update(shipment_id=entry['shipment_id'])

    return JsonResponse({'status': 'success', 'updated': updated_total})
