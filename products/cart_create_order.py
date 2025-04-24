from .models import Product, ProductImage, PriceList, Price, Cart, CartItem, Order, OrderItem, ProductCategory
from finance.models import Payment
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
from decimal import Decimal
from pprint import pprint

@require_POST
def create_order(request):
    selected_buyer_id = request.session.get('selected_buyer_id')
    selected_buyer = get_user_model().objects.get(id=selected_buyer_id)
    cart_contribution = request.session.get('cart_contribution')
    contribution_usage_array = cart_contribution.get('contribution_usage_array')
    temporary_array_of_all_items = cart_contribution.get('temporary_array_of_all_items')

    if selected_buyer.profile.is_beneficiary and cart_contribution:

        contribution_items_with_assigned_payments = assign_payments_to_contribution_items(contribution_usage_array)
        temporary_array_of_all_items_with_assigned_payments = map_all_items_to_contribution_items(
            temporary_array_of_all_items, contribution_items_with_assigned_payments
        )

        # print("temporary_array_of_all_items_with_assigned_payments:")
        # for item in temporary_array_of_all_items_with_assigned_payments:
        #     print(item)

        grouped_items = group_items_by_payment_id_and_product_id(temporary_array_of_all_items_with_assigned_payments)
        # print("grouped items:")
        # for item in grouped_items:
        #     print(item)


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
        if grouped_items:
            print("grouped items:")
            for item in grouped_items:
                product = Product.objects.get(id=item['product_id'])
                payment = Payment.objects.get(id=item['payment_id'])
                subtotal = item['quantity'] * item['price']
                print("subtotal: " + str(subtotal))

                try:
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=item['quantity'],
                        price=item['price'],
                        payment=payment,
                        subtotal=subtotal
                        )
                except Exception as e:
                    print("error creating order item: " + str(e))
                
                print("order item created: " + str(order_item.id))
        else:
            print("cart items:")
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.price,
                subtotal=cart_item.subtotal
            )

        # Clear the cart
        print("clearing cart")
        cart.delete()

        request.session['cart_open'] = False  # Close cart after successful order
        if 'cart_contribution' in request.session:
            del request.session['cart_contribution']  # Clear cart contribution
        request.session.modified = True
        messages.success(request, 'Zamówienie zostało złożone pomyślnie!')
        return redirect('home')

    except Cart.DoesNotExist:
        messages.error(request, 'Nie znaleziono koszyka')
        return redirect(request.META.get('HTTP_REFERER', 'home'))
    except Exception as e:
        messages.error(request, f'Wystąpił błąd: {str(e)}')
        return redirect(request.META.get('HTTP_REFERER', 'home'))



def assign_payments_to_contribution_items(contribution_usage_array):
    available_contributions = Payment.get_available_contributions()
    order_items_payed_by_contributions_array = []

    for contribution in available_contributions:
        available_amount = contribution.available_amount
        contribution_usage_array_sum = find_sum_of_all_items_with_empty_payment_id(contribution_usage_array)
        if  available_amount >= contribution_usage_array_sum:
            contribution_usage_array = assign_payment_id_to_all_with_empty_payment_id(contribution_usage_array, contribution.id)
            break
        else:
            contribution_usage_array = try_to_use_contribution_to_the_round_number(available_amount, contribution.id, contribution_usage_array)

    return contribution_usage_array

def map_all_items_to_contribution_items(temporary_array_of_all_items, contribution_usage_array):
    # Create a copy of the temporary array to avoid modifying the original
    result_array = [item.copy() for item in temporary_array_of_all_items]
    
    # For each item in contribution_usage_array
    for contribution_item in contribution_usage_array:
        product_id = contribution_item['product_id']
        payment_id = contribution_item['payment_id']
        
        # Find a matching item in temporary_array with empty payment_id
        for item in result_array:
            if (item['product_id'] == product_id and 
                item.get('payment_id', '') == ''):
                # Assign the payment_id from contribution_item
                item['payment_id'] = payment_id
                # Break after finding and updating the first match
                break
    
    return result_array

def try_to_use_contribution_to_the_round_number(available_amount, payment_id, temporary_array_of_all_items):
    # 1. Find all items with empty payment_id
    items_without_payment = [item.copy() for item in temporary_array_of_all_items if item.get('payment_id', '') == '']
    
    # 2. Find a combination of items with sum closest to available_amount (never greater)
    best_combination = []
    best_sum = 0
    
    # Convert prices to Decimal for precise calculations
    items_without_payment_decimal = []
    for item in items_without_payment:
        item_copy = item.copy()
        item_copy['price_decimal'] = Decimal(item['price'])
        items_without_payment_decimal.append(item_copy)
    
    available_amount_decimal = Decimal(str(available_amount))
    
    # Sort items by price in descending order for the algorithm
    items_without_payment_decimal.sort(key=lambda x: x['price_decimal'], reverse=True)
    
    # Try to find optimal solution using dynamic programming
    def find_optimal_subset(items, target_sum):
        n = len(items)
        # Create a table where dp[i][j] stores whether sum j is possible with subset of first i items
        dp = [[False for _ in range(int(target_sum * 100) + 1)] for _ in range(n + 1)]
        
        # Empty subset has sum 0
        for i in range(n + 1):
            dp[i][0] = True
        
        # Fill the dp table
        for i in range(1, n + 1):
            for j in range(1, int(target_sum * 100) + 1):
                # Don't include the current item
                dp[i][j] = dp[i-1][j]
                
                # Include the current item if its value doesn't exceed the current sum
                item_price_cents = int(items[i-1]['price_decimal'] * 100)
                if j >= item_price_cents:
                    dp[i][j] = dp[i][j] or dp[i-1][j-item_price_cents]
        
        # Find the largest sum that is possible and <= target_sum
        best_sum_cents = 0
        for j in range(int(target_sum * 100), -1, -1):
            if dp[n][j]:
                best_sum_cents = j
                break
        
        # Reconstruct the subset that gives this sum
        result = []
        j = best_sum_cents
        for i in range(n, 0, -1):
            # If the current item is part of the solution
            if j > 0 and dp[i][j] and not dp[i-1][j]:
                result.append(items[i-1])
                j -= int(items[i-1]['price_decimal'] * 100)
        
        return result, Decimal(best_sum_cents) / 100
    
    # Find the optimal subset of items
    best_combination, best_sum = find_optimal_subset(items_without_payment_decimal, available_amount_decimal)
    
    # 3. Assign payment_id to the selected items in the original array
    result = []
    for item in temporary_array_of_all_items:
        item_copy = item.copy()
        
        # Check if this item is in the best combination (matches by product_id and has no payment_id)
        for selected_item in best_combination:
            if (item_copy.get('product_id') == selected_item.get('product_id') and 
                item_copy.get('payment_id', '') == '' and 
                Decimal(item_copy['price']) == selected_item['price_decimal']):
                # Assign the payment_id
                item_copy['payment_id'] = payment_id
                # Remove this item from the best combination to avoid assigning payment_id to multiple items
                best_combination.remove(selected_item)
                break
                
        result.append(item_copy)
    
    # 4. Return the updated array
    return result

def assign_payment_id_to_all_with_empty_payment_id(temporary_array_of_all_items, contribution_id):
    used_amount = 0
    for item in temporary_array_of_all_items:
        if item['payment_id'] == '':
            item['payment_id'] = contribution_id
            used_amount += Decimal(item['price'])
    print(">> used amount: " + str(used_amount)+ "<<")        
    return temporary_array_of_all_items

def find_sum_of_all_items_with_empty_payment_id(temporary_array_of_all_items):
    sum = 0
    for item in temporary_array_of_all_items:
        if item['payment_id'] == '':
            sum += Decimal(item['price'])
    return sum

def group_items_by_payment_id_and_product_id(temporary_array_of_all_items):
    grouped_items = {}
    result = []

    for item in temporary_array_of_all_items:
        product_id = item['product_id']
        payment_id = item['payment_id']

        key = f"{product_id}_{payment_id}"

        if key not in grouped_items:
            grouped_items[key] = item.copy()
        else:
            grouped_items[key]['quantity'] += item['quantity']

    for grouped_item in grouped_items.values():
        result.append(grouped_item)

    return result
