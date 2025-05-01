from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from domy.decorators import require_authenticated_staff_or_superuser
from .models import Supplier, SupplyOrder, StockEntry
from finance.models import Invoice
from products.models import Product, OrderItem
from stock.models import StockReduction
from decimal import Decimal
from django.db.models import F, ExpressionWrapper, DecimalField, Sum
import json

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

@require_authenticated_staff_or_superuser
def api_products(request):
    """API endpoint to get products with stock level data for the Vue app"""
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    
    # Get stock information for each product
    product_data = []
    for product in products:
        # Get physical stock
        physical_entries = StockEntry.objects.filter(
            product=product,
            stock_type='physical'
        ).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0
        
        # Get virtual stock
        virtual_entries = StockEntry.objects.filter(
            product=product,
            stock_type='virtual'
        ).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0
        
        product_info = {
            'id': product.id,
            'name': product.name,
            'ean': product.ean,
            'physical_stock': physical_entries,
            'virtual_stock': virtual_entries,
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
        'stock_items': all_items
    }
    
    return JsonResponse(product_data) 
