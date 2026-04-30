from .models import Product, Cart, CartItem, Order, OrderItem
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from stock.models import StockReduction
from django.utils import timezone
from django.contrib import messages


def create_stock_reductions(order, order_items):
    for order_item in order_items:
        StockReduction.objects.create(
            product=order_item.product,
            quantity=1,
            order=order,
            order_item=order_item,
            created_at=timezone.now(),
            stock_type='virtual'
        )


@require_POST
def create_order(request):
    selected_buyer_id = request.session.get('selected_buyer_id')
    if not selected_buyer_id:
        messages.error(request, 'Nie wybrano kupującego')
        return redirect('home')

    try:
        cart = Cart.objects.get(
            user=request.user,
            buyer_id=selected_buyer_id
        )

        order = Order.objects.create(
            user=request.user,
            buyer=cart.buyer,
            total_cost=cart.total_cost,
            max_payable_amount=cart.total_cost,
        )

        order_items = []
        for cart_item in cart.items.all():
            for _ in range(cart_item.quantity):
                order_item = OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    price=cart_item.price,
                )
                order_items.append(order_item)

        create_stock_reductions(order, order_items)
        cart.delete()

        request.session['cart_open'] = False
        if 'cart_contribution' in request.session:
            del request.session['cart_contribution']
        request.session.modified = True
        messages.success(request, 'Zamówienie zostało złożone pomyślnie!')
        return redirect('home')

    except Cart.DoesNotExist:
        messages.error(request, 'Nie znaleziono koszyka')
        return redirect(request.META.get('HTTP_REFERER', 'home'))
    except Exception as e:
        messages.error(request, f'Wystąpił błąd: {str(e)}')
        return redirect(request.META.get('HTTP_REFERER', 'home'))
