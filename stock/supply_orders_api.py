"""API dostaw (SupplyOrder) dla panelu React."""

import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from domy.decorators import require_authenticated_staff_or_superuser
from finance.models import Invoice
from products.models import Product

from .models import StockEntry, Supplier, SupplyOrder


def _decimal_str(value):
    if value is None:
        return None
    return str(value)


def _supply_order_entry_to_dict(entry):
    return {
        'id': entry.id,
        'product_id': entry.product_id,
        'product_name': entry.product.name if entry.product_id else '',
        'quantity': entry.quantity,
        'net_cost': _decimal_str(entry.net_cost),
        'gross_cost': _decimal_str(entry.gross_cost),
        'vat_rate': _decimal_str(entry.vat_rate),
        'total_net_cost': _decimal_str(entry.total_net_cost),
        'total_gross_cost': _decimal_str(entry.total_gross_cost),
        'stock_type': entry.stock_type,
        'stock_type_display': entry.get_stock_type_display(),
    }


def _supply_order_to_dict(supply_order):
    entries = list(supply_order.stock_entries.all())
    invoice = supply_order.invoice
    return {
        'id': supply_order.id,
        'order_number': supply_order.order_number or '',
        'created_at': supply_order.created_at.isoformat() if supply_order.created_at else None,
        'supplier': {
            'id': supply_order.supplier_id,
            'name': supply_order.supplier.name if supply_order.supplier_id else '',
        },
        'invoice': (
            {
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'gross_price': _decimal_str(invoice.gross_price),
            }
            if invoice
            else None
        ),
        'total_net_cost': _decimal_str(supply_order.get_total_net_cost()),
        'total_gross_cost': _decimal_str(supply_order.get_total_gross_cost()),
        'stock_entries': [_supply_order_entry_to_dict(e) for e in entries],
    }


def _invoice_to_dict(invoice):
    return {
        'id': invoice.id,
        'invoice_number': invoice.invoice_number,
        'gross_price': _decimal_str(invoice.gross_price),
        'supplier_id': invoice.supplier_id,
    }


def _product_option_to_dict(product):
    return {
        'id': product.id,
        'name': product.name,
        'vat': _decimal_str(product.vat),
    }


@require_GET
@require_authenticated_staff_or_superuser
def api_list_supply_orders(request):
    """Lista dostaw + dane pomocnicze do formularza dodawania."""
    entries_qs = StockEntry.objects.select_related('product').order_by('id')
    supply_orders = (
        SupplyOrder.objects.select_related('supplier', 'invoice')
        .prefetch_related(Prefetch('stock_entries', queryset=entries_qs))
        .order_by('-created_at')
    )

    unassigned_invoices = Invoice.objects.filter(supply_orders__isnull=True).select_related(
        'supplier'
    )
    suppliers = Supplier.objects.all().order_by('name')
    products = Product.objects.filter(is_active=True).order_by('name')

    return JsonResponse(
        {
            'supply_orders': [_supply_order_to_dict(so) for so in supply_orders],
            'suppliers': [{'id': s.id, 'name': s.name} for s in suppliers],
            'unassigned_invoices': [_invoice_to_dict(inv) for inv in unassigned_invoices],
            'products': [_product_option_to_dict(p) for p in products],
        },
        json_dumps_params={'ensure_ascii': False},
    )


def _parse_stock_entries(raw_entries):
    if not isinstance(raw_entries, list) or not raw_entries:
        return None, JsonResponse({'detail': 'stock_entries must be a non-empty list'}, status=400)

    parsed = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            return None, JsonResponse({'detail': 'stock_entries item must be an object'}, status=400)
        try:
            product_id = int(entry.get('product_id'))
            quantity = int(entry.get('quantity'))
            net_cost = Decimal(str(entry.get('net_cost')))
            gross_cost = Decimal(str(entry.get('gross_cost')))
            stock_type = (entry.get('stock_type') or '').strip()
            vat_rate = Decimal(str(entry.get('vat_rate', 0)))
        except (TypeError, ValueError, InvalidOperation):
            return None, JsonResponse({'detail': 'Invalid stock_entries item'}, status=400)

        if product_id <= 0 or quantity <= 0:
            return None, JsonResponse({'detail': 'Invalid product_id or quantity'}, status=400)
        if stock_type not in ('physical', 'virtual'):
            return None, JsonResponse({'detail': 'Invalid stock_type'}, status=400)

        parsed.append(
            {
                'product_id': product_id,
                'quantity': quantity,
                'net_cost': net_cost,
                'gross_cost': gross_cost,
                'stock_type': stock_type,
                'vat_rate': vat_rate,
            }
        )
    return parsed, None


@require_POST
@require_authenticated_staff_or_superuser
def api_create_supply_order(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    supplier_id = data.get('supplier_id')
    if not isinstance(supplier_id, int) or supplier_id <= 0:
        return JsonResponse({'detail': 'Invalid supplier_id'}, status=400)

    supplier = get_object_or_404(Supplier, id=supplier_id)

    invoice_id = data.get('invoice_id')
    invoice = None
    if invoice_id is not None and invoice_id != '':
        if not isinstance(invoice_id, int) or invoice_id <= 0:
            return JsonResponse({'detail': 'Invalid invoice_id'}, status=400)
        invoice = get_object_or_404(Invoice, id=invoice_id)
        if invoice.supply_orders.exists():
            return JsonResponse(
                {'detail': 'Ta faktura jest już przypisana do innego zamówienia'},
                status=400,
            )
        if invoice.supplier_id != supplier.id:
            return JsonResponse(
                {'detail': 'Ta faktura należy do innego dostawcy'},
                status=400,
            )

    parsed_entries, err = _parse_stock_entries(data.get('stock_entries'))
    if err is not None:
        return err

    product_ids = {e['product_id'] for e in parsed_entries}
    existing_ids = set(
        Product.objects.filter(id__in=product_ids, is_active=True).values_list('id', flat=True)
    )
    if existing_ids != product_ids:
        return JsonResponse({'detail': 'One or more products not found'}, status=404)

    if invoice:
        total_gross = sum(e['gross_cost'] * e['quantity'] for e in parsed_entries)
        if total_gross != invoice.gross_price:
            return JsonResponse(
                {
                    'detail': (
                        f'Kwota faktury ({invoice.gross_price} zł) nie zgadza się '
                        f'z sumą dostawy ({total_gross} zł)'
                    )
                },
                status=400,
            )

    try:
        with transaction.atomic():
            supply_order = SupplyOrder.objects.create(supplier=supplier, invoice=invoice)
            for entry in parsed_entries:
                product = Product.objects.get(id=entry['product_id'])
                StockEntry.objects.create(
                    product=product,
                    supply_order=supply_order,
                    quantity=entry['quantity'],
                    net_cost=entry['net_cost'],
                    gross_cost=entry['gross_cost'],
                    stock_type=entry['stock_type'],
                    vat_rate=entry['vat_rate'],
                )
    except Exception as exc:
        return JsonResponse({'detail': str(exc)}, status=400)

    supply_order = (
        SupplyOrder.objects.select_related('supplier', 'invoice')
        .prefetch_related(
            Prefetch(
                'stock_entries',
                queryset=StockEntry.objects.select_related('product').order_by('id'),
            )
        )
        .get(id=supply_order.id)
    )
    return JsonResponse(
        {'status': 'success', 'supply_order': _supply_order_to_dict(supply_order)},
        status=201,
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_delete_supply_order(request, supply_order_id):
    supply_order = get_object_or_404(SupplyOrder, id=supply_order_id)
    with transaction.atomic():
        supply_order.stock_entries.all().delete()
        supply_order.delete()
    return JsonResponse({'status': 'success', 'supply_order_id': supply_order_id})


@require_POST
@require_authenticated_staff_or_superuser
def api_assign_supply_order_invoice(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    supply_order_id = data.get('supply_order_id')
    invoice_id = data.get('invoice_id')
    if not isinstance(supply_order_id, int) or supply_order_id <= 0:
        return JsonResponse({'detail': 'Invalid supply_order_id'}, status=400)
    if not isinstance(invoice_id, int) or invoice_id <= 0:
        return JsonResponse({'detail': 'Invalid invoice_id'}, status=400)

    supply_order = get_object_or_404(
        SupplyOrder.objects.select_related('supplier', 'invoice').prefetch_related('stock_entries'),
        id=supply_order_id,
    )
    if supply_order.invoice_id:
        return JsonResponse({'detail': 'Dostawa ma już przypisaną fakturę'}, status=400)

    invoice = get_object_or_404(Invoice, id=invoice_id)
    if invoice.supply_orders.exists():
        return JsonResponse(
            {'detail': 'Ta faktura jest już przypisana do innego zamówienia'},
            status=400,
        )
    if invoice.supplier_id != supply_order.supplier_id:
        return JsonResponse({'detail': 'Ta faktura należy do innego dostawcy'}, status=400)

    total_gross = supply_order.get_total_gross_cost()
    if invoice.gross_price != total_gross:
        return JsonResponse(
            {
                'detail': (
                    f'Kwota faktury ({invoice.gross_price} zł) nie zgadza się '
                    f'z sumą dostawy ({total_gross} zł)'
                )
            },
            status=400,
        )

    supply_order.invoice = invoice
    supply_order.save(update_fields=['invoice'])

    supply_order = (
        SupplyOrder.objects.select_related('supplier', 'invoice')
        .prefetch_related(
            Prefetch(
                'stock_entries',
                queryset=StockEntry.objects.select_related('product').order_by('id'),
            )
        )
        .get(id=supply_order.id)
    )
    return JsonResponse(
        {'status': 'success', 'supply_order': _supply_order_to_dict(supply_order)},
        json_dumps_params={'ensure_ascii': False},
    )
