from .models import Product, ProductImage, PriceList, Price, Cart, CartItem, Order, OrderItem, ProductCategory
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from domy.decorators import require_authenticated_staff_or_superuser
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
import json
import decimal
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum, F
from stock.models import StockEntry, StockReduction
from django.utils import timezone
from finance.models import MonthlyContributionUsage
from stock.views import calculate_physical_stock_level, calculate_virtual_stock_level
from .orders_api import get_order_with_items

@require_authenticated_staff_or_superuser
def products(request):
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    categories = ProductCategory.objects.all()
    
    # Get stock information for each product
    for product in products:
        product.physical_stock = calculate_physical_stock_level(product)
        product.virtual_stock = calculate_virtual_stock_level(product)

    return render(request, 'products/products.html', {
        'products': products,
        'categories': categories
    })

@require_authenticated_staff_or_superuser
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            ProductCategory.objects.create(name=name)
            return HttpResponseRedirect(reverse('products'))
    return HttpResponseBadRequest("Invalid request")

@require_authenticated_staff_or_superuser
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        vat = request.POST.get('vat')
        ean = request.POST.get('ean')
        volume_value = request.POST.get('volume_value')
        volume_unit = request.POST.get('volume_unit')
        categories = request.POST.getlist('categories')

        if name:
            product = Product.objects.create(
                name=name,
                description=description,
                vat=vat,
                ean=ean,
                volume_value=volume_value,
                volume_unit=volume_unit
            )

            if categories:
                product.categories.set(categories)

            # Handle image upload
            if 'image' in request.FILES:
                image_file = request.FILES['image']
                ProductImage.objects.create(
                    product=product,
                    image=image_file
                )

            price_lists = PriceList.objects.all()
            for price_list in price_lists:
                Price.objects.create(
                    price_list=price_list,
                    product=product,
                    net_price=0,
                    gross_price=0
                )

            return HttpResponseRedirect(reverse('products'))

    return HttpResponseBadRequest("Invalid request")

@require_authenticated_staff_or_superuser
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product.name = request.POST.get('name', product.name)
        product.description = request.POST.get('description', product.description)
        product.vat = request.POST.get('vat', product.vat)
        product.ean = request.POST.get('ean', product.ean)
        product.volume_value = request.POST.get('volume_value', product.volume_value)
        product.volume_unit = request.POST.get('volume_unit', product.volume_unit)

        # Handle image upload
        if 'image' in request.FILES:
            image_file = request.FILES['image']
            # Delete all existing images
            product.images.all().delete()
            # Create new image
            ProductImage.objects.create(
                product=product,
                image=image_file
            )

        # Handle categories
        categories = request.POST.getlist('categories')
        product.categories.set(categories)

        product.save()
        return HttpResponseRedirect(reverse('products'))

    return render(request, 'products/edit_product.html', {'product': product})

@require_authenticated_staff_or_superuser
def prices(request):
    price_lists = PriceList.objects.all()
    products = Product.objects.filter(is_active=True)
    return render(request, 'products/prices.html', {
        'price_lists': price_lists,
        'products': products
    })

@require_POST
@require_authenticated_staff_or_superuser
def add_price_list(request):
    name = request.POST.get('name')
    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)

    price_list = PriceList.objects.create(name=name)

    # Create empty prices for all products
    products = Product.objects.filter(is_active=True)
    for product in products:
        Price.objects.create(
            price_list=price_list,
            product=product,
            net_price=0,
            gross_price=0
        )

    return JsonResponse({
        'price_list_id': price_list.id,
        'status': 'success',
        'name': price_list.name
    })

@require_POST
@require_authenticated_staff_or_superuser
def save_price(request):
    data = json.loads(request.body)
    price_list_id = data.get('price_list_id')
    product_id = data.get('product_id')
    net_price = data.get('net_price')
    gross_price = data.get('gross_price')

    if not all([price_list_id, product_id, net_price, gross_price]):
        return JsonResponse({'status': 'error', 'error': 'Missing required fields'}, status=400)

    try:
        price = Price.objects.get(
            price_list_id=price_list_id,
            product_id=product_id
        )
        price.net_price = net_price
        price.gross_price = gross_price
        price.save()
        return JsonResponse({
            'status': 'success',
            'data': {
                'net_price': str(price.net_price),
                'gross_price': str(price.gross_price)
            }
        })
    except Price.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Price not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

def home(request):
    products = Product.objects.filter(is_active=True).prefetch_related('images', 'prices')
    User = get_user_model()
    context = {
        'products': products,
    }
    
    selected_buyer = None  # Initialize the variable

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            beneficiaries = User.objects.filter(profile__is_beneficiary=True)
            context['beneficiaries'] = beneficiaries

            selected_buyer_id = request.session.get('selected_buyer_id')
            if selected_buyer_id:
                try:
                    selected_buyer = User.objects.get(id=selected_buyer_id)
                    context['selected_buyer'] = selected_buyer
                    
                    # Get the buyer's price list
                    buyer_price_list = selected_buyer.profile.price_list
                    if buyer_price_list:
                        prices = Price.objects.filter(
                            price_list=buyer_price_list,
                            product__in=products
                        ).select_related('product')
                        
                        product_prices = {price.product_id: price.gross_price for price in prices}
                        context['product_prices'] = product_prices
                except User.DoesNotExist:
                    pass
        else:
            selected_buyer = request.user
            context['selected_buyer'] = selected_buyer
            buyer_price_list = request.user.profile.price_list
            if buyer_price_list:
                prices = Price.objects.filter(
                    price_list=buyer_price_list,
                    product__in=products
                ).select_related('product')
                product_prices = {price.product_id: price.gross_price for price in prices}
                context['product_prices'] = product_prices

        if selected_buyer:
            current_date = timezone.now()
            monthly_usage = selected_buyer.profile.get_or_create_monthly_usage(
                year=current_date.year,
                month=current_date.month
            )
        else:
            monthly_usage = None
        context['monthly_usage'] = monthly_usage

    return render(request, 'home.html', context)

@require_POST
@require_authenticated_staff_or_superuser
def change_buyer(request):
    buyer_id = request.POST.get('buyer_id')


    if buyer_id:
        request.session['selected_buyer_id'] = buyer_id
        User = get_user_model()
        try:
            buyer = User.objects.get(id=buyer_id)
            price_list_id = buyer.profile.price_list_id if buyer.profile.price_list else None

            # Get cart data for the selected buyer
            cart = Cart.objects.filter(user=request.user, buyer=buyer).first()
            cart_data = None
            if cart:
                cart_data = {
                    'items': [{
                        'id': item.id,
                        'name': item.product.name,
                        'quantity': item.quantity,
                        'price': str(item.price),
                        'subtotal': str(item.subtotal),
                        'image_url': item.product.images.first().image.url if item.product.images.exists() else None
                    } for item in cart.items.all()],
                    'total_cost': str(cart.total_cost)
                }
            
            return JsonResponse({
                'status': 'success',
                'price_list_id': price_list_id,
                'cart_data': cart_data
            })
        except User.DoesNotExist:
            pass
    else:
        request.session.pop('selected_buyer_id', None)
    
    return JsonResponse({'status': 'success'})

def orders(request):
    User = get_user_model()
    context = {}

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            # Get all beneficiary users for staff/superuser
            beneficiaries = User.objects.filter(profile__is_beneficiary=True)
            context['beneficiaries'] = beneficiaries
            
            # Get all contributor users for staff/superuser
            contributors = User.objects.filter(profile__is_contributor=True)
            context['contributors'] = contributors
            
            # Get selected buyer or default to None
            selected_buyer_id = request.session.get('selected_buyer_id')
            if selected_buyer_id:
                try:
                    selected_buyer = User.objects.get(id=selected_buyer_id)
                    context['selected_buyer'] = selected_buyer
                    orders = Order.objects.filter(buyer=selected_buyer).prefetch_related(
                        'items__product__images'
                    ).order_by('-created_at')
                    context['orders'] = orders
                except User.DoesNotExist:
                    pass
        else:
            # Regular user sees their own orders
            orders = Order.objects.filter(buyer=request.user).prefetch_related(
                'items__product__images'
            ).order_by('-created_at')
            context['orders'] = orders
            
            # Regular users might also need the contributors list for the dropdown
            contributors = User.objects.filter(profile__is_contributor=True)
            context['contributors'] = contributors

    return render(request, 'products/orders.html', context)

@require_authenticated_staff_or_superuser
def all_orders(request):
    # Get all orders for staff/superuser
    User = get_user_model()
    orders = Order.objects.all().prefetch_related(
        'items__product__images',
        'buyer'
    ).order_by('-created_at')
    
    context = {
        'orders': orders,
    }
    
    return render(request, 'products/all_orders.html', context)

@require_authenticated_staff_or_superuser
def api_get_all_orders(request):
    User = get_user_model()
    orders = Order.objects.all().prefetch_related(
        'items__product',
        'items__stock_reductions',
        'items__payments',
        'buyer__profile'
    ).order_by('-created_at')
    
    # Format the orders for JSON response
    orders_data = []
    for order in orders:
        items_data = []
        for item in order.items.all():
            stock_reductions = []
            for reduction in item.stock_reductions.all():
                stock_reductions.append({
                    'id': reduction.id,
                    'stock_type': reduction.stock_type,
                    'quantity': reduction.quantity
                })
                
            payments = []
            for payment in item.payments.all():
                payments.append({
                    'id': payment.id
                })
                
            items_data.append({
                'id': item.id,
                'product_id': item.product.id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price': float(item.price),
                'subtotal': float(item.subtotal),
                'buyer_id': item.buyer.id if item.buyer else None,
                'stock_reductions': stock_reductions,
                'payments': payments
            })
        
        buyer_name = order.buyer.profile.name if order.buyer and hasattr(order.buyer, 'profile') and order.buyer.profile.name else order.buyer.username
            
        orders_data.append({
            'id': order.id,
            'created_at': order.created_at.strftime('%d.%m.%Y %H:%M'),
            'status': order.status,
            'total_cost': float(order.total_cost),
            'unpaid_amount': float(order.unpaid_amount),
            'buyer_id': order.buyer.id,
            'buyer_name': buyer_name,
            'items': items_data
        })
    
    # Get all buyers
    buyers = User.objects.filter(profile__is_beneficiary=True)
    buyers_data = []
    for buyer in buyers:
        buyers_data.append({
            'id': buyer.id,
            'name': buyer.profile.name if hasattr(buyer, 'profile') and buyer.profile.name else buyer.username
        })
    
    # Return JSON response
    return JsonResponse({
        'orders': orders_data,
        'buyers': buyers_data,
        'is_staff': request.user.is_staff or request.user.is_superuser
    })

@require_POST
@require_authenticated_staff_or_superuser
def update_order_status(request):
    data = json.loads(request.body)
    order_id = data.get('order_id')
    new_status = data.get('status')
    
    try:
        order = Order.objects.get(id=order_id)
        order.status = new_status
        order.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Status zamówienia został zaktualizowany'
        })
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Zamówienie nie zostało znalezione'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_POST
@require_authenticated_staff_or_superuser
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return JsonResponse({'status': 'success'})

@require_POST
@require_authenticated_staff_or_superuser
def delete_order(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
        order.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Zamówienie zostało usunięte'
        })
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Zamówienie nie zostało znalezione'
        }, status=404)

@require_POST
def assign_buyer_to_order_item(request):
    try:
        data = json.loads(request.body)
        order_item_id = data.get('order_item_id')
        buyer_id = data.get('buyer_id')
        
        if not order_item_id:
            return JsonResponse({
                'status': 'error',
                'message': 'ID elementu zamówienia jest wymagane'
            }, status=400)
            
        order_item = get_object_or_404(OrderItem, id=order_item_id)
        
        if buyer_id:
            buyer = get_object_or_404(get_user_model(), id=buyer_id)
            order_item.buyer = buyer
        else:
            order_item.buyer = None
            
        order_item.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Płacący został przypisany pomyślnie'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_authenticated_staff_or_superuser
def settle_order(request, order_id):
    """
    View for settling an order with the given order_id.
    """
    # Get the order or return 404
    order = get_object_or_404(Order, id=order_id)
    
    context = {
        'order_id': order_id,
    }
    
    return render(request, 'products/settle_order.html', context)

@require_authenticated_staff_or_superuser
def api_get_order_details(request, order_id):
    """
    API view to get details of a specific order
    """
    order_data = get_order_with_items(order_id)
    
    if order_data is None:
        return JsonResponse({
            'status': 'error',
            'message': 'Order not found'
        }, status=404)
    
    return JsonResponse(order_data)

@require_POST
@require_authenticated_staff_or_superuser
def api_submit_payment(request):
    """
    API view to submit a payment for an order
    """
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        amount = data.get('amount')
        payment_method = data.get('payment_method', 'cash')
        
        if not all([order_id, amount]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            }, status=400)
        
        # Convert amount to Decimal
        try:
            amount = decimal.Decimal(str(amount))
        except (decimal.InvalidOperation, TypeError):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid amount'
            }, status=400)
        
        # Get the order
        try:
            order = Order.objects.prefetch_related('items').get(id=order_id)
        except Order.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Order not found'
            }, status=404)
        
        # Check if amount is valid
        if amount <= 0 or amount > order.unpaid_amount:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid payment amount'
            }, status=400)
        
        # Import Payment model
        from finance.models import Payment
        
        # Create a payment record
        payment = Payment.objects.create(
            amount=amount,
            payment_type='order',
            description=f'Payment for order #{order.id}',
            related_user=order.buyer,
            related_order=order,
            created_by=request.user,
            payment_date=timezone.now().date()
        )
        
        # Update the order's unpaid amount (assuming unpaid_amount is a field on the Order model)
        # If not, you may need to add this field or calculate it differently
        if hasattr(order, 'unpaid_amount'):
            order.unpaid_amount -= amount
            order.save()
        
        # Assign payment to unpaid order items
        remaining_payment = amount
        unpaid_items = []
        
        # First, gather all unpaid or partially paid items
        for item in order.items.all():
            # Calculate how much has been paid for this item
            paid_amount = item.payments.aggregate(total=Sum('amount'))['total'] or 0
            
            # If item is not fully paid, add to unpaid_items list
            if paid_amount < item.subtotal:
                unpaid_items.append({
                    'item': item,
                    'unpaid': item.subtotal - paid_amount
                })
        
        # Then allocate payment to items
        for unpaid_item in unpaid_items:
            item = unpaid_item['item']
            unpaid_amount = unpaid_item['unpaid']
            
            if remaining_payment <= 0:
                break
                
            # Determine how much to allocate to this item
            to_pay = min(unpaid_amount, remaining_payment)
            
            # Add item to payment's related_order_items
            payment.related_order_items.add(item)
            
            # Reduce remaining payment
            remaining_payment -= to_pay
        
        return JsonResponse({
            'status': 'success',
            'payment_id': payment.id,
            'remaining_amount': str(order.unpaid_amount if hasattr(order, 'unpaid_amount') else 0)
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

