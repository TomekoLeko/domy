"""API faktur (Invoice) dla panelu React."""

import json
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from domy.decorators import require_authenticated_staff_or_superuser
from stock.models import StockEntry, Supplier, SupplyOrder
from stock.supply_orders_api import _decimal_str, _supply_order_entry_to_dict

from .models import Invoice

_ALLOWED_SORT = frozenset(
    {
        'invoice_number',
        'supplier_name',
        'net_price',
        'gross_price',
        'created_at',
        '-invoice_number',
        '-supplier_name',
        '-net_price',
        '-gross_price',
        '-created_at',
    }
)


def _supply_order_for_invoice_dict(supply_order):
    entries = list(supply_order.stock_entries.all())
    return {
        'id': supply_order.id,
        'order_number': supply_order.order_number or '',
        'total_net_cost': _decimal_str(supply_order.get_total_net_cost()),
        'total_gross_cost': _decimal_str(supply_order.get_total_gross_cost()),
        'stock_entries': [_supply_order_entry_to_dict(e) for e in entries],
    }


def _invoice_to_dict(invoice):
    supply_orders = list(invoice.supply_orders.all())
    return {
        'id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'supplier_id': invoice.supplier_id,
        'supplier_name': invoice.supplier_name,
        'net_price': _decimal_str(invoice.net_price),
        'vat_rate': _decimal_str(invoice.vat_rate),
        'gross_price': _decimal_str(invoice.gross_price),
        'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
        'supply_orders_count': getattr(invoice, 'supply_orders_count', len(supply_orders)),
        'supply_orders': [_supply_order_for_invoice_dict(so) for so in supply_orders],
    }


def _invoices_queryset():
    entries_qs = StockEntry.objects.select_related('product').order_by('id')
    return (
        Invoice.objects.annotate(supply_orders_count=Count('supply_orders'))
        .prefetch_related(
            Prefetch(
                'supply_orders',
                queryset=SupplyOrder.objects.prefetch_related(
                    Prefetch('stock_entries', queryset=entries_qs)
                ).order_by('id'),
            )
        )
    )


@require_GET
@require_authenticated_staff_or_superuser
def api_list_invoices(request):
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by not in _ALLOWED_SORT:
        sort_by = '-created_at'

    search_query = (request.GET.get('search') or '').strip()

    invoices = _invoices_queryset()
    if search_query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search_query) | Q(supplier_name__icontains=search_query)
        )
    invoices = invoices.order_by(sort_by)

    suppliers = Supplier.objects.all().order_by('name')

    return JsonResponse(
        {
            'invoices': [_invoice_to_dict(inv) for inv in invoices],
            'suppliers': [{'id': s.id, 'name': s.name} for s in suppliers],
            'current_sort': sort_by,
            'search_query': search_query,
        },
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_create_invoice(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    invoice_number = (data.get('invoice_number') or '').strip()
    supplier_id = data.get('supplier_id')
    gross_price_raw = data.get('gross_price')

    if not invoice_number or supplier_id is None or gross_price_raw is None:
        return JsonResponse(
            {'status': 'error', 'message': 'Wszystkie pola są wymagane.'},
            status=400,
        )

    try:
        supplier_id = int(supplier_id)
        gross_price = Decimal(str(gross_price_raw))
    except (TypeError, ValueError, InvalidOperation):
        return JsonResponse(
            {'status': 'error', 'message': 'Nieprawidłowe dane formularza.'},
            status=400,
        )

    if supplier_id <= 0:
        return JsonResponse(
            {'status': 'error', 'message': 'Wybierz dostawcę.'},
            status=400,
        )

    supplier = get_object_or_404(Supplier, id=supplier_id)

    try:
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            supplier=supplier,
            gross_price=gross_price,
        )
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

    invoice = _invoices_queryset().get(id=invoice.id)
    return JsonResponse(
        {
            'status': 'success',
            'invoice_id': invoice.id,
            'invoice': _invoice_to_dict(invoice),
        },
        status=201,
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_delete_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    try:
        for supply_order in invoice.supply_orders.all():
            supply_order.invoice = None
            supply_order.save(update_fields=['invoice'])
        invoice.delete()
        return JsonResponse({'status': 'success'})
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
