from .models import Product, ProductImage, PriceList, Price, Cart, CartItem, Order, OrderItem, ProductCategory
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from domy.decorators import require_authenticated_staff_or_superuser
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum, F
from stock.models import StockEntry, StockReduction
from django.utils import timezone
from finance.models import MonthlyContributionUsage
from django.contrib import messages

@require_POST
def update_cart(request):
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    buyer_id = request.POST.get('buyer_id')

    try:
        if product_id and buyer_id:
            # Verify buyer is currently selected
            if str(buyer_id) != str(request.session.get('selected_buyer_id')):
                messages.error(request, 'Nieprawidłowy kupujący')
                return redirect('home')
            buyer = get_user_model().objects.get(id=buyer_id)
            product = Product.objects.get(id=product_id)

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
            # Check if product already in cart
            cart_item = CartItem.objects.filter(
                cart=cart,
                product=product
            ).first()

            if cart_item:
                cart_item.quantity = cart_item.quantity + quantity
                if cart_item.quantity > 0:
                    cart_item.save()
                else:
                    cart_item.delete()

                messages.success(request, 'Koszyk zaktualizowany')
            else:
                # Create new item
                cart_item = CartItem.objects.create(
                    cart=cart,
                    product=product,
                    quantity=quantity,
                    price=price.gross_price
                )

            messages.success(request, 'Produkt dodany do koszyka')

        else:
            messages.error(request, 'Nieprawidłowe parametry')
            return redirect('home')

        return redirect(request.META.get('HTTP_REFERER', 'home'))

    except (Product.DoesNotExist, get_user_model().DoesNotExist, Price.DoesNotExist, CartItem.DoesNotExist) as e:
        messages.error(request, str(e))
        return redirect(request.META.get('HTTP_REFERER', 'home'))
    except Exception as e:
        messages.error(request, f'Wystąpił błąd: {str(e)}')
        return redirect(request.META.get('HTTP_REFERER', 'home'))


def determine_contribution_usage(buyer_id):
    try:
        #  get buyer's cart
        cart = Cart.objects.get(buyer_id=buyer_id)
        # get cart items
        cart_items = CartItem.objects.filter(cart=cart)

        # Create temporary array with individual entries for each product unit
        temporary_array = []
        for cart_item in cart_items:
            # Get product details
            product_id = cart_item.product.id
            product_name = cart_item.product.name
            price = str(cart_item.price)  # Convert Decimal to string for safe serialization

            # Add an entry to the temporary array for each unit of quantity
            for _ in range(cart_item.quantity):
                temporary_array.append({
                    'product_id': product_id,
                    'product_name': product_name,
                    'price': price
                })

        # Get the latest monthly_contribution_usage for the user
        buyer = cart.buyer
        monthly_contribution_usage = MonthlyContributionUsage.objects.filter(
            profile__user=buyer
        ).order_by('-year', '-month').first()

        if not monthly_contribution_usage:
            return temporary_array, []

        remaining_limit = monthly_contribution_usage.remaining_limit

        # Create contribution_usage_array based on the requirements
        contribution_usage_array = []

        # Calculate the total value of temporary_array to determine 50% limit
        total_cart_value = sum(float(item['price']) for item in temporary_array)
        fifty_percent_limit = total_cart_value * 0.5
 
        # Determine the effective limit (the lower of the two limits)
        effective_limit = min(float(remaining_limit), fifty_percent_limit)

        # Sort temporary_array by price (descending) to optimize usage of the limit
        # Using descending sort to get closest to the limit with fewer items
        sorted_temp_array = sorted(temporary_array, key=lambda x: float(x['price']), reverse=True)

        contribution_usage_array, current_sum = assign_greedy(temporary_array, effective_limit)


        return temporary_array, contribution_usage_array
    except (Cart.DoesNotExist, MonthlyContributionUsage.DoesNotExist):
        return [], []
        

def assign_greedy(temporary_array, effective_limit):
    sorted_temp_array = sorted(temporary_array, key=lambda x: float(x['price']), reverse=True)

    current_sum = 0.0
    contribution_usage_array = []

    for item in sorted_temp_array:
        item_price = float(item['price'])
        if current_sum + item_price <= effective_limit:
            contribution_usage_array.append(item)
            current_sum += item_price

    return contribution_usage_array, current_sum

@require_POST
def remove_cart_item(request):
    product_id = request.POST.get('product_id')
    buyer_id = request.POST.get('buyer_id')

    try:
        if product_id and buyer_id:
            # Verify buyer is currently selected
            if str(buyer_id) != str(request.session.get('selected_buyer_id')):
                messages.error(request, 'Nieprawidłowy kupujący')
                return redirect('home')
            buyer = get_user_model().objects.get(id=buyer_id)
            product = Product.objects.get(id=product_id)

            # Get or create cart for this specific buyer
            cart = Cart.objects.get(
                user=request.user,
                buyer=buyer
            )

            # Check if product already in cart
            cart_item = CartItem.objects.filter(
                cart=cart,
                product=product
            ).first()

            if cart_item:
                cart_item.delete()

                messages.success(request, 'Koszyk zaktualizowany')
            else:
                messages.error(request, 'Nie ma takiego produktu w koszyku')
                

            messages.success(request, 'Produkt usunięty z koszyka')

        else:
            messages.error(request, 'Nieprawidłowe parametry')
            return redirect('home')

        return redirect(request.META.get('HTTP_REFERER', 'home'))

    except (Product.DoesNotExist, get_user_model().DoesNotExist, Price.DoesNotExist, CartItem.DoesNotExist) as e:
        messages.error(request, str(e))
        return redirect(request.META.get('HTTP_REFERER', 'home'))
    except Exception as e:
        messages.error(request, f'Wystąpił błąd: {str(e)}')
        return redirect(request.META.get('HTTP_REFERER', 'home'))

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
        return redirect(request.META.get('HTTP_REFERER', 'home'))
    except Exception as e:
        messages.error(request, f'Wystąpił błąd: {str(e)}')
        return redirect(request.META.get('HTTP_REFERER', 'home'))

@csrf_exempt
@require_POST
def toggle_cart(request):
    request.session['cart_open'] = not request.session.get('cart_open', False)
    request.session.modified = True
    return JsonResponse({'status': 'success', 'cart_open': request.session['cart_open']})
