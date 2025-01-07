from .models import Product, ProductImage, PriceList, Price, Cart, CartItem, Order, OrderItem
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from domy.decorators import require_authenticated_staff_or_superuser
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
import json
from django.contrib.auth import get_user_model
from django.db.models import Q

@require_authenticated_staff_or_superuser
def products(request):
    products = Product.objects.filter(is_active=True)
    return render(request, 'products/products.html', {'products': products})

@require_authenticated_staff_or_superuser
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')

        image = request.FILES.get('image')

        if not name:
            return HttpResponseBadRequest("Missing required fields.")

        product = Product.objects.create(
            name=name,
            description=description,
        )

        if image:
            product.images.create(image=image)

        return HttpResponseRedirect(reverse('products'))

    return HttpResponseBadRequest("Invalid request method.")

@require_authenticated_staff_or_superuser
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product.name = request.POST.get('name', product.name)
        product.description = request.POST.get('description', product.description)

        if 'image' in request.FILES:
            uploaded_image = request.FILES['image']

            existing_images = product.images.all()
            if existing_images.exists():
                image_instance = existing_images.first()
                image_instance.image = uploaded_image
                image_instance.save()
            else:
                ProductImage.objects.create(product=product, image=uploaded_image)

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

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            beneficiaries = User.objects.filter(profile__is_beneficiary=True)
            print("Beneficiaries count:", beneficiaries.count())
            for b in beneficiaries:
                print(f"User: {b.username}, is_beneficiary: {b.profile.is_beneficiary}")
            context['beneficiaries'] = beneficiaries

            selected_buyer_id = request.session.get('selected_buyer_id')
            if selected_buyer_id:
                try:
                    selected_buyer = User.objects.get(id=selected_buyer_id)
                    context['selected_buyer'] = selected_buyer
                    print(f"Selected buyer: {selected_buyer.username}")
                    print(f"Buyer's price list: {selected_buyer.profile.price_list}")
                except User.DoesNotExist:
                    pass
        else:
            # Regular user is their own buyer
            context['selected_buyer'] = request.user
            print(f"Regular user as buyer: {request.user.username}")
            print(f"User's price list: {request.user.profile.price_list}")

        if 'selected_buyer' in context:
            cart = Cart.objects.filter(
                user=request.user,
                buyer=context['selected_buyer']
            ).first()
            if cart:
                context['cart'] = cart

    # Debug print products and their prices
    for product in products:
        print(f"Product: {product.name}")
        print(f"Prices: {[p for p in product.prices.all()]}")

    return render(request, 'home.html', context)

@require_POST
def add_to_cart(request):
    data = json.loads(request.body)
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))
    buyer_id = data.get('buyer_id')

    if not all([product_id, quantity, buyer_id]):
        return JsonResponse({'error': 'Missing required fields'}, status=400)

    try:
        product = Product.objects.get(id=product_id)
        buyer = get_user_model().objects.get(id=buyer_id)

        # Get or create cart
        cart, created = Cart.objects.get_or_create(
            user=request.user,
            buyer=buyer
        )
        # Get price for the buyer
        price_list = buyer.profile.price_list
        if not price_list:
            return JsonResponse({'error': 'No price list assigned to buyer'}, status=400)

        price = Price.objects.get(price_list=price_list, product=product)

        # Add or update cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'price': price.gross_price}
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        # Prepare cart data for response
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
            'cart_count': cart.total_items,
            'cart_total': str(cart.total_cost),
            'cart_data': cart_data
        })

    except (Product.DoesNotExist, get_user_model().DoesNotExist, Price.DoesNotExist) as e:
        return JsonResponse({'error': str(e)}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_POST
def update_cart(request):
    data = json.loads(request.body)
    item_id = data.get('item_id')
    quantity = int(data.get('quantity', 0))

    try:
        cart_item = CartItem.objects.get(id=item_id)

        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()

        cart = cart_item.cart

        return JsonResponse({
            'status': 'success',
            'cart_count': cart.total_items,
            'cart_total': str(cart.total_cost),
            'item_subtotal': str(cart_item.subtotal) if quantity > 0 else '0'
        })

    except CartItem.DoesNotExist:
        return JsonResponse({'error': 'Cart item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_POST
def create_order(request):
    try:
        # Get the cart for the current user
        cart = Cart.objects.get(user=request.user)

        # Create order
        order = Order.objects.create(
            user=request.user,
            buyer=cart.buyer,
            total_cost=cart.total_cost
        )

        # Create order items
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                price=cart_item.price,
                subtotal=cart_item.subtotal
            )

        # Clear the cart
        cart.delete()

        return JsonResponse({
            'status': 'success',
            'order_id': order.id
        })

    except Cart.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'No active cart found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@require_authenticated_staff_or_superuser
def change_buyer(request):
    data = json.loads(request.body)
    buyer_id = data.get('buyer_id')

    if buyer_id:
        request.session['selected_buyer_id'] = buyer_id
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

    return render(request, 'products/orders.html', context)

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

