from .models import Product, ProductImage, PriceList, Price, Cart, CartItem, Order, OrderItem, ProductCategory
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from domy.decorators import require_authenticated_staff_or_superuser
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from django.contrib.auth import get_user_model
from django.contrib import messages

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
    """
    Return contribution usage data for the current cart.
    The frontend expects `cart_contribution` in the response.
    """
    try:
        cart_contribution = request.session.get('cart_contribution')
        return JsonResponse({
            'status': 'success',
            'cart_contribution': cart_contribution
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

