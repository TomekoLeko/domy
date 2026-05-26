from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from domy.decorators import require_authenticated_staff_or_superuser
from .models import Supplier, SupplyOrder, StockEntry
from finance.models import Invoice
from products.models import Product, Order, OrderItem
from stock.models import StockReduction
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import F, ExpressionWrapper, DecimalField, Sum
from django.utils.dateparse import parse_datetime
from django.utils import timezone
import json
from pprint import pprint

@require_authenticated_staff_or_superuser
def suppliers(request):
    suppliers = Supplier.objects.all().order_by('-created_at')
    return render(request, 'stock/suppliers.html', {
        'suppliers': suppliers
    })

@require_POST
@require_authenticated_staff_or_superuser
def add_supplier(request):
    name = request.POST.get('name')
    address = request.POST.get('address')
    postal = request.POST.get('postal')
    city = request.POST.get('city')
    mail = request.POST.get('mail')
    phone = request.POST.get('phone')
    nip = request.POST.get('nip')

    if name:
        supplier = Supplier.objects.create(
            name=name,
            address=address,
            postal=postal,
            city=city,
            mail=mail,
            phone=phone,
            nip=nip
        )
        return JsonResponse({
            'status': 'success',
            'supplier_id': supplier.id,
            'name': supplier.name
        })
    return JsonResponse({'status': 'error', 'message': 'Name is required'}, status=400)

@require_POST
@require_authenticated_staff_or_superuser
def edit_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)
    
    supplier.name = request.POST.get('name', supplier.name)
    supplier.address = request.POST.get('address', supplier.address)
    supplier.postal = request.POST.get('postal', supplier.postal)
    supplier.city = request.POST.get('city', supplier.city)
    supplier.mail = request.POST.get('mail', supplier.mail)
    supplier.phone = request.POST.get('phone', supplier.phone)
    supplier.nip = request.POST.get('nip', supplier.nip)
    
    supplier.save()
    return JsonResponse({'status': 'success'})

@require_POST
@require_authenticated_staff_or_superuser
def delete_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)
    supplier.delete()
    return JsonResponse({'status': 'success'})

@require_authenticated_staff_or_superuser
def stock_main(request):
    return render(request, 'stock/main.html', {
        'suppliers': Supplier.objects.all(),
        'invoices': Invoice.objects.filter(supply_orders__isnull=True),
        'products': Product.objects.filter(is_active=True),
        'supply_orders': SupplyOrder.objects.all().select_related(
            'supplier', 
            'invoice'
        ).prefetch_related(
            'stock_entries',
            'stock_entries__product'
        ).distinct().order_by('-created_at')
    })

@require_POST
@require_authenticated_staff_or_superuser
def add_supply_order(request):
    try:
        supplier_id = request.POST.get('supplier')
        invoice_id = request.POST.get('invoice')
        stock_entries = json.loads(request.POST.get('stock_entries', '[]'))

        supplier = Supplier.objects.get(id=supplier_id)
        invoice = None if not invoice_id else Invoice.objects.get(id=invoice_id)

        if invoice and invoice.supply_orders.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'Ta faktura jest już przypisana do innego zamówienia'
            }, status=400)

        supply_order = SupplyOrder.objects.create(
            supplier=supplier,
            invoice=invoice
        )

        for entry in stock_entries:
            product = Product.objects.get(id=entry['product_id'])
            StockEntry.objects.create(
                product=product,
                supply_order=supply_order,
                quantity=entry['quantity'],
                net_cost=Decimal(entry['net_cost']),
                gross_cost=Decimal(entry['gross_cost']),
                stock_type=entry['stock_type'],
                vat_rate=entry['vat_rate']
            )

        return JsonResponse({
            'status': 'success',
            'supply_order_id': supply_order.id
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@require_POST
@require_authenticated_staff_or_superuser
def assign_invoice(request):
    try:
        data = json.loads(request.body)
        supply_order = get_object_or_404(SupplyOrder, id=data['supply_order_id'])
        invoice = get_object_or_404(Invoice, id=data['invoice_id'])

        # Verify invoice isn't already assigned and belongs to same supplier
        if invoice.supply_orders.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'Ta faktura jest już przypisana do innego zamówienia'
            }, status=400)

        if invoice.supplier_id != supply_order.supplier_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Ta faktura należy do innego dostawcy'
            }, status=400)

        supply_order.invoice = invoice
        supply_order.save()

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@require_POST
@require_authenticated_staff_or_superuser
def delete_supply_order(request, supply_order_id):
    try:
        supply_order = get_object_or_404(SupplyOrder, id=supply_order_id)
        
        # Delete all related stock entries first
        supply_order.stock_entries.all().delete()
        
        # Then delete the supply order
        supply_order.delete()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@require_POST
@require_authenticated_staff_or_superuser
def create_stock_reduction(request):
    try:
        data = json.loads(request.body)
        order_item_id = data.get('order_item_id')
        product_id = data.get('product_id')
        quantity = data.get('quantity')
        stock_type = data.get('stock_type')
        
        # Ensure quantity is an integer
        if isinstance(quantity, str):
            quantity = int(quantity)  # Convert to integer if it's a string
        
        # Get the order item
        order_item = get_object_or_404(OrderItem, id=order_item_id)
        
        # Create the stock reduction
        stock_reduction = StockReduction.objects.create(
            product_id=product_id,
            order=order_item.order,
            order_item=order_item,
            quantity=quantity,
            stock_type=stock_type
        )
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@require_authenticated_staff_or_superuser
def stock_levels(request):
    """View to display the current stock levels of products"""
    return render(request, 'stock/stock_levels.html') 

def calculate_physical_stock_level(product):
    physical_entries_total = StockEntry.objects.filter(
        product=product,
        stock_type='physical'
    ).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    
    physical_reductions_total = StockReduction.objects.filter(
        product=product,
        stock_type='physical'
    ).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    
    return physical_entries_total - physical_reductions_total

def calculate_virtual_stock_level(product):
    virtual_entries_total = StockEntry.objects.filter(
        product=product,
        stock_type='virtual'
    ).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    
    virtual_reductions_total = StockReduction.objects.filter(
        product=product,
        stock_type='virtual'
    ).aggregate(
        total=Sum('quantity')
    )['total'] or 0
    
    return virtual_entries_total - virtual_reductions_total

def _stock_reduction_to_dict(reduction):
    return {
        'id': reduction.id,
        'created_at': reduction.created_at.isoformat() if reduction.created_at else None,
        'product_id': reduction.product_id,
        'product_name': reduction.product.name if reduction.product_id else '',
        'order_id': reduction.order_id,
        'order_item_id': reduction.order_item_id,
        'quantity': reduction.quantity,
        'stock_type': reduction.stock_type,
        'stock_type_display': reduction.get_stock_type_display(),
        'stock_entry_id': reduction.stock_entry_id,
        'issuing_cost': (
            str(reduction.issuing_cost.quantize(Decimal('0.01')))
            if reduction.issuing_cost is not None
            else None
        ),
    }


def _parse_optional_int(value, field_name, *, required=False, min_value=None):
    if value is None or value == '':
        if required:
            return None, JsonResponse(
                {'detail': f'Pole {field_name} jest wymagane.'},
                status=400,
                json_dumps_params={'ensure_ascii': False},
            )
        return None, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, JsonResponse(
            {'detail': f'Nieprawidłowa wartość pola {field_name}.'},
            status=400,
            json_dumps_params={'ensure_ascii': False},
        )
    if min_value is not None and parsed < min_value:
        return None, JsonResponse(
            {'detail': f'Pole {field_name} musi być >= {min_value}.'},
            status=400,
            json_dumps_params={'ensure_ascii': False},
        )
    return parsed, None


def _parse_optional_decimal(value, field_name):
    if value is None or value == '':
        return None, None
    try:
        return Decimal(str(value).replace(',', '.')), None
    except (InvalidOperation, ValueError):
        return None, JsonResponse(
            {'detail': f'Nieprawidłowa wartość pola {field_name}.'},
            status=400,
            json_dumps_params={'ensure_ascii': False},
        )


@require_GET
@require_authenticated_staff_or_superuser
def api_list_stock_reductions(request):
    """Lista wszystkich wydań towaru z magazynu."""
    reductions = (
        StockReduction.objects.select_related('product', 'order', 'order_item', 'stock_entry')
        .order_by('-created_at')
    )
    data = [_stock_reduction_to_dict(reduction) for reduction in reductions]
    return JsonResponse(
        {'reductions': data},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_update_stock_reduction(request, reduction_id):
    """Aktualizuje wydanie magazynowe (bez logiki FIFO z `StockReduction.save`)."""
    reduction = get_object_or_404(StockReduction, id=reduction_id)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    product_id, err = _parse_optional_int(data.get('product_id'), 'product_id', required=True)
    if err:
        return err
    order_id, err = _parse_optional_int(data.get('order_id'), 'order_id', required=True)
    if err:
        return err
    quantity, err = _parse_optional_int(data.get('quantity'), 'quantity', required=True, min_value=1)
    if err:
        return err

    stock_type = data.get('stock_type')
    if stock_type not in dict(StockReduction.STOCK_TYPE_CHOICES):
        return JsonResponse(
            {'detail': 'Nieprawidłowy typ magazynu.'},
            status=400,
            json_dumps_params={'ensure_ascii': False},
        )

    order_item_id, err = _parse_optional_int(data.get('order_item_id'), 'order_item_id')
    if err:
        return err
    stock_entry_id, err = _parse_optional_int(data.get('stock_entry_id'), 'stock_entry_id')
    if err:
        return err

    issuing_cost, err = _parse_optional_decimal(data.get('issuing_cost'), 'issuing_cost')
    if err:
        return err

    if not Product.objects.filter(pk=product_id).exists():
        return JsonResponse({'detail': 'Nie znaleziono produktu.'}, status=400)
    if not Order.objects.filter(pk=order_id).exists():
        return JsonResponse({'detail': 'Nie znaleziono zamówienia.'}, status=400)

    if order_item_id is not None:
        order_item = get_object_or_404(OrderItem, pk=order_item_id)
        if order_item.order_id != order_id:
            return JsonResponse(
                {'detail': 'Pozycja zamówienia nie należy do wskazanego zamówienia.'},
                status=400,
                json_dumps_params={'ensure_ascii': False},
            )
        if order_item.product_id != product_id:
            return JsonResponse(
                {'detail': 'Produkt pozycji zamówienia nie zgadza się z produktem wydania.'},
                status=400,
                json_dumps_params={'ensure_ascii': False},
            )

    if stock_entry_id is not None:
        stock_entry = get_object_or_404(StockEntry, pk=stock_entry_id)
        if stock_entry.product_id != product_id:
            return JsonResponse(
                {'detail': 'Wpis magazynowy dotyczy innego produktu.'},
                status=400,
                json_dumps_params={'ensure_ascii': False},
            )

    created_at_raw = data.get('created_at')
    created_at = None
    if created_at_raw not in (None, ''):
        created_at = parse_datetime(str(created_at_raw))
        if created_at is None:
            return JsonResponse(
                {'detail': 'Nieprawidłowa data utworzenia.'},
                status=400,
                json_dumps_params={'ensure_ascii': False},
            )
        if timezone.is_naive(created_at):
            created_at = timezone.make_aware(created_at, timezone.get_current_timezone())

    old_stock_entry_id = reduction.stock_entry_id

    update_kwargs = {
        'product_id': product_id,
        'order_id': order_id,
        'order_item_id': order_item_id,
        'quantity': quantity,
        'stock_type': stock_type,
        'stock_entry_id': stock_entry_id,
        'issuing_cost': issuing_cost,
    }
    if created_at is not None:
        update_kwargs['created_at'] = created_at

    with transaction.atomic():
        StockReduction.objects.filter(pk=reduction_id).update(**update_kwargs)
        affected_entry_ids = {eid for eid in (old_stock_entry_id, stock_entry_id) if eid is not None}
        for entry_id in affected_entry_ids:
            _recalculate_stock_entry_remaining_quantity(entry_id)

    reduction.refresh_from_db()
    return JsonResponse(
        {'status': 'success', 'reduction': _stock_reduction_to_dict(reduction)},
        json_dumps_params={'ensure_ascii': False},
    )


def _recalculate_stock_entry_remaining_quantity(stock_entry_id):
    """Ustawia remaining_quantity na podstawie sumy powiązanych redukcji."""
    entry = StockEntry.objects.get(id=stock_entry_id)
    used = (
        StockReduction.objects.filter(stock_entry_id=stock_entry_id).aggregate(
            total=Sum('quantity')
        )['total']
        or 0
    )
    entry.remaining_quantity = max(entry.quantity - used, 0)
    entry.save(update_fields=['remaining_quantity'])


@require_POST
@require_authenticated_staff_or_superuser
def api_delete_stock_reduction(request, reduction_id):
    """Usuwa redukcję magazynową i przelicza wpis magazynowy, jeśli był powiązany."""
    reduction = get_object_or_404(StockReduction, id=reduction_id)
    stock_entry_id = reduction.stock_entry_id
    deleted_id = reduction.id

    with transaction.atomic():
        reduction.delete()
        if stock_entry_id is not None:
            _recalculate_stock_entry_remaining_quantity(stock_entry_id)

    return JsonResponse(
        {'status': 'success', 'reduction_id': deleted_id},
        json_dumps_params={'ensure_ascii': False},
    )


@require_authenticated_staff_or_superuser
def api_products(request):
    products = Product.objects.filter(
        is_active=True,
        is_service=False,
        exclude_from_catalog=False,
    ).prefetch_related('images')
    
    # Get stock information for each product
    product_data = []
    for product in products:
        physical_stock_level = calculate_physical_stock_level(product)
        virtual_stock_level = calculate_virtual_stock_level(product)

        product_info = {
            'id': product.id,
            'name': product.name,
            'ean': product.ean,
            'physical_stock_level': physical_stock_level,
            'virtual_stock_level': virtual_stock_level,
            'unit': product.get_volume_unit_display()
        }

        product_data.append(product_info)

    return JsonResponse({'products': product_data}) 

@require_authenticated_staff_or_superuser
def product_stock_levels(request, product_id):
    """View to display detailed stock information for a specific product"""
    product = get_object_or_404(Product, id=product_id)
    
    return render(request, 'stock/product_stock_levels.html', {
        'product': product,
    })

@require_authenticated_staff_or_superuser
def api_product_stock_data(request, product_id):
    """API endpoint to get detailed stock data for a specific product"""
    product = get_object_or_404(Product, id=product_id)
    
    # Get stock entries
    stock_entries = StockEntry.objects.filter(product=product).select_related('supply_order', 'supply_order__supplier')
    
    # Get stock reductions
    stock_reductions = StockReduction.objects.filter(product=product).select_related('order', 'order_item')
    
    # Calculate stock levels using the separate methods
    physical_stock_level = calculate_physical_stock_level(product)
    virtual_stock_level = calculate_virtual_stock_level(product)
    
    entries_data = []
    for entry in stock_entries:
        entries_data.append({
            'id': entry.id,
            'type': 'entry',
            'date': entry.created_at.strftime('%Y-%m-%d %H:%M'),
            'quantity': entry.quantity,
            'remaining_quantity': entry.remaining_quantity,
            'supplier': entry.supply_order.supplier.name if entry.supply_order.supplier else 'N/A',
            'stock_type': entry.get_stock_type_display(),
            'order_number': entry.supply_order.order_number if entry.supply_order.order_number else 'N/A',
        })
    
    reductions_data = []
    for reduction in stock_reductions:
        reductions_data.append({
            'id': reduction.id,
            'type': 'reduction',
            'date': reduction.created_at.strftime('%Y-%m-%d %H:%M'),
            'quantity': reduction.quantity,
            'order_id': reduction.order.id if reduction.order else 'N/A',
            'stock_type': reduction.get_stock_type_display(),
        })
    
    # Combine and sort by date (newest first)
    all_items = entries_data + reductions_data
    
    product_data = {
        'id': product.id,
        'name': product.name,
        'ean': product.ean,
        'physical_stock_level': physical_stock_level,
        'virtual_stock_level': virtual_stock_level,
        'stock_items': all_items
    }
    print("product_data: ")
    pprint(product_data)
    
    return JsonResponse(product_data) 
