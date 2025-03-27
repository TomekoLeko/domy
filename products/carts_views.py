from .models import Product, ProductImage, PriceList, Price, Cart, CartItem, Order, OrderItem, ProductCategory
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from domy.decorators import require_authenticated_staff_or_superuser
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
import json
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum, F
from stock.models import StockEntry, StockReduction
from django.utils import timezone
from finance.models import MonthlyContributionUsage

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
        
        # Verify this is the currently selected buyer
        if str(buyer_id) != str(request.session.get('selected_buyer_id')):
            return JsonResponse({'error': 'Invalid buyer selected'}, status=400)

        # Get or create cart for this specific buyer
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
        cart_item = CartItem.objects.filter(
            cart=cart,
            product=product
        ).first()

        if cart_item:
            cart_item.quantity += quantity
            cart_item.save()
        else:
            cart_item = CartItem.objects.create(
                cart=cart,
                product=product,
                quantity=quantity,
                price=price.gross_price
            )

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
        print(f"Error in add_to_cart: {str(e)}")  # Add debugging
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
        # Get the selected buyer's ID from session
        selected_buyer_id = request.session.get('selected_buyer_id')
        if not selected_buyer_id:
            return JsonResponse({
                'status': 'error', 
                'message': 'No buyer selected'
            }, status=400)

        # Get the specific cart for the current user and selected buyer
        cart = Cart.objects.get(
            user=request.user,
            buyer_id=selected_buyer_id
        )

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
        return JsonResponse({
            'status': 'error', 
            'message': 'No active cart found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': str(e)
        }, status=500)
