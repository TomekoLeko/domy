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
from django.contrib import messages

@require_POST
def add_to_cart(request):
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    buyer_id = request.POST.get('buyer_id')

    if not all([product_id, quantity, buyer_id]):
        messages.error(request, 'Brak wymaganych danych')
        return redirect('home')

    try:
        product = Product.objects.get(id=product_id)
        buyer = get_user_model().objects.get(id=buyer_id)
        
        # Verify this is the currently selected buyer
        if str(buyer_id) != str(request.session.get('selected_buyer_id')):
            messages.error(request, 'Nieprawidłowy kupujący')
            return redirect('home')

        # Get or create cart for this specific buyer
        cart, created = Cart.objects.get_or_create(
            user=request.user,
            buyer=buyer
        )

        # Get price for the buyer
        price_list = buyer.profile.price_list
        if not price_list:
            messages.error(request, 'Brak cennika dla kupującego')
            return redirect('home')

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

        request.session['cart_open'] = True
        request.session.modified = True
        messages.success(request, 'Produkt dodany do koszyka')
        return redirect('home')

    except (Product.DoesNotExist, get_user_model().DoesNotExist, Price.DoesNotExist) as e:
        messages.error(request, str(e))
        return redirect('home')
    except Exception as e:
        messages.error(request, f'Wystąpił błąd: {str(e)}')
        return redirect('home')

@require_POST
def update_cart(request):
    item_id = request.POST.get('item_id')
    quantity = int(request.POST.get('quantity', 0))

    try:
        cart_item = CartItem.objects.get(id=item_id)

        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()

        request.session['cart_open'] = True
        request.session.modified = True
        messages.success(request, 'Koszyk zaktualizowany')
        return redirect('home')

    except CartItem.DoesNotExist:
        messages.error(request, 'Nie znaleziono pozycji w koszyku')
        return redirect('home')
    except Exception as e:
        messages.error(request, f'Wystąpił błąd: {str(e)}')
        return redirect('home')

@require_POST
def create_order(request):
    try:
        # Get the selected buyer's ID from session
        selected_buyer_id = request.session.get('selected_buyer_id')
        if not selected_buyer_id:
            messages.error(request, 'Nie wybrano kupującego')
            return redirect('home')

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

        request.session['cart_open'] = False  # Close cart after successful order
        request.session.modified = True
        messages.success(request, 'Zamówienie zostało złożone pomyślnie!')
        return redirect('home')

    except Cart.DoesNotExist:
        messages.error(request, 'Nie znaleziono koszyka')
        return redirect(request.META.get('HTTP_REFERER', 'home') + '?cart=open')
    except Exception as e:
        messages.error(request, f'Wystąpił błąd: {str(e)}')
        return redirect(request.META.get('HTTP_REFERER', 'home') + '?cart=open')

@require_POST
def toggle_cart(request):
    request.session['cart_open'] = not request.session.get('cart_open', False)
    request.session.modified = True
    return redirect('home')
