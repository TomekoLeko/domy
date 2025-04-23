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

@csrf_exempt
@require_POST
def update_cart(request):
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    buyer_id = request.POST.get('buyer_id')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

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

        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'Produkt dodany do koszyka'})
        else:
            return redirect(request.META.get('HTTP_REFERER', 'home'))

    except (Product.DoesNotExist, get_user_model().DoesNotExist, Price.DoesNotExist, CartItem.DoesNotExist) as e:
        messages.error(request, str(e))
        return redirect(request.META.get('HTTP_REFERER', 'home'))
    except Exception as e:
        messages.error(request, f'Wystąpił błąd: {str(e)}')
        return redirect(request.META.get('HTTP_REFERER', 'home'))

@csrf_exempt
@require_POST
def remove_cart_item(request):
    product_id = request.POST.get('product_id')
    buyer_id = request.POST.get('buyer_id')

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

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
                

            if is_ajax:
                return JsonResponse({'status': 'success', 'message': 'Produkt usunięty z koszyka'})
            else:
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


def map_available_contributions_to_contribution_usage_array(contribution_usage_array, temporary_array_of_all_items):
    available_contributions = Payment.get_available_contributions()
    order_items_payed_by_contributions_array = []
    # map temporary_array_of_all_items and give it buyer_id (empyt for now)
    temporary_array_of_all_items = [{**item, 'payment_id': ''} for item in temporary_array_of_all_items]

    # pprint(temporary_array_of_all_items)
    # PRÓBUJEMY ZUZYĆ CAŁĄ KONTRYBUCJĘ I JEELI SIE NIE DA TO PRZEGHODZIMY DO KOLEJNEJ (FIFO)
    # NA TEN MOMENT ZRÓBMY KOLEKCJĘ, POTEM ORDER ITEMS

    for contribution in available_contributions:
        available_amount = contribution.available_amount
        contribution_usage_array_sum = sum(float(item['price']) for item in contribution_usage_array)
        print('First contribution available_amount: ' + str(available_amount))
        print('First contribution contribution_usage_array_sum: ' + str(contribution_usage_array_sum))

        if  available_amount >= contribution_usage_array_sum:
            for item in contribution_usage_array:
                temporary_array_of_all_items = find_item_and_assign_payment_id(temporary_array_of_all_items, item, contribution.id)
            print('Ended with one payment')
            for item in temporary_array_of_all_items:
                print(item)
            print('///////////////////////////////////////////')

            break
        else:
            print('Using the: ' + str(contribution.id) + ' payment to the round number')
            temporary_array_of_all_items = try_to_use_contribution_to_the_round_number(available_amount, contribution.id, temporary_array_of_all_items)
            #try tu use the whole contribution to the round number
            # take available amount, payment_id, temporary_array_of_all_items, assign payemtns, return new temporary_array_of_all_items
            for item in temporary_array_of_all_items:
                print(item)
            print('--------------------------------')










        # for item in contribution_usage_array:
        #     if available_amount >= Decimal(item['price']):
        #         order_item = {
        #             'product_id': item['product_id'],
        #             'product_name': item['product_name'],
        #             'price': item['price'],
        #             'quantity': 1,
        #             'payment_id': contribution.id
        #         }
        #         order_items_payed_by_contributions_array.append(order_item)
        #         contribution_usage_array.remove(item)
        #         available_amount -= Decimal(item['price'])
        #     else:
        #         break
               
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

def find_item_and_assign_payment_id(temporary_array_of_all_items, item, contribution_id):
    used_amount = 0
    for item in temporary_array_of_all_items:
        if item['product_id'] == item['product_id'] and item['payment_id'] == '':
            item['payment_id'] = contribution_id
            used_amount += Decimal(item['price'])

    print(">> used amount: " + str(used_amount)+ "<<")        
    return temporary_array_of_all_items

@require_POST
def create_order(request):
    selected_buyer_id = request.session.get('selected_buyer_id')
    selected_buyer = get_user_model().objects.get(id=selected_buyer_id)

    cart_contribution = request.session.get('cart_contribution')
    if selected_buyer.profile.is_beneficiary and cart_contribution:
        # get the cart_contribution from the session

        map_available_contributions_to_contribution_usage_array(
            cart_contribution.get('contribution_usage_array'), cart_contribution.get('temporary_array_of_all_items')
        )


        #  MAP AVAILABLE CONTRIBUTIONS TO CONTRIBUTION USAGE ARRAY



    
    else:
        print('selected_buyer is not beneficiary')
    return redirect(request.META.get('HTTP_REFERER', 'home'))

    # try:
    #     # Get the selected buyer's ID from session
    #     selected_buyer_id = request.session.get('selected_buyer_id')
    #     if not selected_buyer_id:
    #         messages.error(request, 'Nie wybrano kupującego')
    #         return redirect('home')

    #     # Get the specific cart for the current user and selected buyer
    #     cart = Cart.objects.get(
    #         user=request.user,
    #         buyer_id=selected_buyer_id
    #     )

    #     # Create order
    #     order = Order.objects.create(
    #         user=request.user,
    #         buyer=cart.buyer,
    #         total_cost=cart.total_cost
    #     )

    #     # Create order items
    #     for cart_item in cart.items.all():
    #         OrderItem.objects.create(
    #             order=order,
    #             product=cart_item.product,
    #             quantity=cart_item.quantity,
    #             price=cart_item.price,
    #             subtotal=cart_item.subtotal
    #         )

    #     # Clear the cart
    #     cart.delete()

    #     request.session['cart_open'] = False  # Close cart after successful order
    #     if 'cart_contribution' in request.session:
    #         del request.session['cart_contribution']  # Clear cart contribution
    #     request.session.modified = True
    #     messages.success(request, 'Zamówienie zostało złożone pomyślnie!')
    #     return redirect('home')

    # except Cart.DoesNotExist:
    #     messages.error(request, 'Nie znaleziono koszyka')
    #     return redirect(request.META.get('HTTP_REFERER', 'home'))
    # except Exception as e:
    #     messages.error(request, f'Wystąpił błąd: {str(e)}')
    #     return redirect(request.META.get('HTTP_REFERER', 'home'))

@csrf_exempt
@require_POST
def toggle_cart(request):
    request.session['cart_open'] = not request.session.get('cart_open', False)
    request.session.modified = True
    return JsonResponse({'status': 'success', 'cart_open': request.session['cart_open']})

@csrf_exempt
@require_POST
def get_cart_items(request):
    try:
        buyer_id = request.POST.get('buyer_id')
        if not buyer_id:
            return JsonResponse({'status': 'error', 'message': 'Nie wybrano kupującego'})

        # get cart items
        cart_items = CartItem.objects.filter(cart__buyer_id=buyer_id)
 
        # Format cart items for JSON response
        items_data = []
        total_cost = 0

        for item in cart_items:
            item_data = {
                'id': item.id,
                'product_id': item.product.id,
                'product_name': item.product.name,
                'price': str(item.price),
                'quantity': item.quantity,
                'subtotal': str(item.subtotal)
            }

            # Add image URL if available
            if item.product.images.exists():
                item_data['image_url'] = item.product.images.first().image.url

            items_data.append(item_data)
            total_cost += float(item.subtotal)

        # Get cart total
        cart = Cart.objects.filter(buyer_id=buyer_id).first()
        cart_total = str(cart.total_cost) if cart else str(total_cost)

        return JsonResponse({
            'status': 'success', 
            'cart_items': items_data,
            'cart_total': cart_total
        })
    except Exception as e:
        print(f"Error in get_cart_items: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)})

@csrf_exempt
@require_POST
def determine_contribution_usage(request):
    buyer_id = request.POST.get('buyer_id')
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

        remaining_limit = determine_remaining_available_limit(cart.buyer)

        # Create contribution_usage_array based on the requirements
        contribution_usage_array = []

        # Calculate the total value of temporary_array to determine 50% limit
        total_cart_value = sum(float(item['price']) for item in temporary_array)
        fifty_percent_limit = total_cart_value * 0.5

        effective_limit = determine_current_effective_limit(cart.buyer, remaining_limit, fifty_percent_limit)

        # Sort temporary_array by price (descending) to optimize usage of the limit
        # Using descending sort to get closest to the limit with fewer items
        sorted_temp_array = sorted(temporary_array, key=lambda x: float(x['price']), reverse=True)

        contribution_usage_array, current_sum = assign_greedy(temporary_array, effective_limit)
        if current_sum != effective_limit:
            contribution_usage_array, current_sum = assign_optimal(temporary_array, effective_limit)

        cart_contribution = {
            'contribution_usage_array': contribution_usage_array,
            'temporary_array_of_all_items': temporary_array,
            'current_sum': current_sum,
            'effective_limit': effective_limit,
            'remaining_limit': str(remaining_limit),
            'fifty_percent_limit': fifty_percent_limit
        }

        # Save cart_contribution in the session
        request.session['cart_contribution'] = cart_contribution
        request.session.modified = True

        return JsonResponse({
            'status': 'success',
            'cart_contribution': cart_contribution
        })

    except (Cart.DoesNotExist, MonthlyContributionUsage.DoesNotExist):
        return JsonResponse({
            'status': 'error',
            'message': 'Cart or contribution usage not found'
        })

def determine_remaining_available_limit(buyer):
    monthly_contribution_usage = MonthlyContributionUsage.objects.filter(
        profile__user=buyer
    ).order_by('-year', '-month').first()

    remaining_available_limit = min(monthly_contribution_usage.remaining_limit, determine_sum_of_available_contributions())

    return remaining_available_limit

def determine_current_effective_limit(buyer, remaining_limit, fifty_percent_limit):
    monthly_contribution_usage = MonthlyContributionUsage.objects.filter(
        profile__user=buyer
    ).order_by('-year', '-month').first()
    if not monthly_contribution_usage:
        return 0

    remaining_limit = monthly_contribution_usage.remaining_limit
    effective_limit = min(float(remaining_limit), fifty_percent_limit)

    #  get sum of all the contributions
    effective_limit = int(effective_limit / 10) * 10
    return effective_limit


def determine_sum_of_available_contributions():
    # hardcoded for now (do not change withoud an explicit command)
    return 200

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

def assign_optimal(temporary_array, effective_limit):
    n = len(temporary_array)
    prices = [float(item['price']) for item in temporary_array]

    # dp[i] = best sum achievable <= i
    dp = [0.0] * (int(effective_limit * 100) + 1)  # scale to avoid floating point errors
    item_trace = [None] * len(dp)  # remember the last item used to get this sum

    for idx, price in enumerate(prices):
        price_cents = int(price * 100)
        for i in range(len(dp) - 1, price_cents - 1, -1):
            if dp[i - price_cents] + price > dp[i]:
                dp[i] = dp[i - price_cents] + price
                item_trace[i] = idx

    # Find the best total
    best_sum_index = max(range(len(dp)), key=lambda i: dp[i])
    best_sum = dp[best_sum_index]

    # Reconstruct the items used
    contribution_usage_array = []
    i = best_sum_index
    while i > 0 and item_trace[i] is not None:
        idx = item_trace[i]
        contribution_usage_array.append(temporary_array[idx])
        price_cents = int(prices[idx] * 100)
        i -= price_cents

    return contribution_usage_array[::-1], best_sum

