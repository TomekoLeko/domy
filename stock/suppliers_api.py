"""API dostawców (Supplier) dla panelu React."""

import json

from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from domy.decorators import require_authenticated_staff_or_superuser

from .models import Supplier


def _supplier_to_dict(supplier):
    return {
        'id': supplier.id,
        'name': supplier.name,
        'address': supplier.address or '',
        'postal': supplier.postal or '',
        'city': supplier.city or '',
        'mail': supplier.mail or '',
        'phone': supplier.phone or '',
        'nip': supplier.nip or '',
        'created_at': supplier.created_at.isoformat() if supplier.created_at else None,
    }


def _parse_supplier_payload(data):
    return {
        'name': (data.get('name') or '').strip(),
        'address': (data.get('address') or '').strip(),
        'postal': (data.get('postal') or '').strip(),
        'city': (data.get('city') or '').strip(),
        'mail': (data.get('mail') or '').strip(),
        'phone': (data.get('phone') or '').strip(),
        'nip': (data.get('nip') or '').strip(),
    }


@require_GET
@require_authenticated_staff_or_superuser
def api_list_suppliers(request):
    suppliers = Supplier.objects.all().order_by('-created_at')
    return JsonResponse(
        {'suppliers': [_supplier_to_dict(s) for s in suppliers]},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_add_supplier(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    payload = _parse_supplier_payload(data)
    if not payload['name']:
        return JsonResponse({'detail': 'name is required'}, status=400)

    supplier = Supplier.objects.create(**payload)
    return JsonResponse(
        {'status': 'success', 'supplier': _supplier_to_dict(supplier)},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_edit_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    payload = _parse_supplier_payload(data)
    if not payload['name']:
        return JsonResponse({'detail': 'name is required'}, status=400)

    for field, value in payload.items():
        setattr(supplier, field, value)
    supplier.save()

    return JsonResponse(
        {'status': 'success', 'supplier': _supplier_to_dict(supplier)},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_delete_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)
    try:
        supplier.delete()
    except IntegrityError:
        return JsonResponse(
            {
                'detail': 'Nie można usunąć dostawcy powiązanego z zamówieniami lub fakturami.',
            },
            status=400,
        )

    return JsonResponse({'status': 'success'})
