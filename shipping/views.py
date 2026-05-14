import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from domy.decorators import require_authenticated_staff_or_superuser

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


@require_POST
@require_authenticated_staff_or_superuser
def api_create_shipment(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    carrier = (data.get('carrier') or '').strip()
    if carrier not in Carrier.values:
        return JsonResponse({'detail': 'Invalid carrier'}, status=400)

    delivery_method = (data.get('delivery_method') or '').strip()
    if delivery_method not in DeliveryMethod.values:
        return JsonResponse({'detail': 'Invalid delivery_method'}, status=400)

    payload = {
        'carrier': carrier,
        'delivery_method': delivery_method,
    }
    for field in REQUIRED_SHIPMENT_FIELDS:
        value = (data.get(field) or '').strip()
        if not value:
            return JsonResponse({'detail': f'{field} is required'}, status=400)
        payload[field] = value

    for field in OPTIONAL_SHIPMENT_FIELDS:
        payload[field] = (data.get(field) or '').strip()

    shipment = Shipment.objects.create(**payload)

    return JsonResponse(
        {'status': 'success', 'shipment': _shipment_to_dict(shipment)},
        json_dumps_params={'ensure_ascii': False},
    )


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
