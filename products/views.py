from .models import Product, ProductImage, PriceList, Price, Cart, CartItem, Order, OrderItem, ProductCategory
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from domy.decorators import require_authenticated_staff_or_superuser
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
import json
from decimal import Decimal, InvalidOperation
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum, F
from django.db import transaction
from stock.models import StockEntry, StockReduction
from django.utils import timezone
from finance.models import Payment, SettlementAllocation
from stock.views import calculate_physical_stock_level, calculate_virtual_stock_level
from users.models import Profile

def _price_list_to_dict(request, price_list):
    prices_data = []
    for price in price_list.prices.select_related('product').prefetch_related('product__images').all():
        first_image = price.product.images.first()
        image_url = None
        if first_image and first_image.image:
            image_url = request.build_absolute_uri(first_image.image.url)
        prices_data.append({
            'product_id': price.product_id,
            'product_name': price.product.name,
            'image_url': image_url,
            'vat': str(price.product.vat),
            'net_price': str(price.net_price),
            'gross_price': str(price.gross_price),
        })

    return {
        'id': price_list.id,
        'name': price_list.name,
        'is_standard': bool(price_list.is_standard),
        'prices': prices_data,
    }


def _admin_product_to_dict(request, product):
    first_image = product.images.first()
    image_url = None
    if first_image and first_image.image:
        image_url = request.build_absolute_uri(first_image.image.url)

    return {
        'id': product.id,
        'name': product.name,
        'description': product.description or '',
        'vat': str(product.vat),
        'ean': product.ean or '',
        'volume_value': str(product.volume_value),
        'volume_unit': product.volume_unit,
        'volume_unit_display': product.get_volume_unit_display(),
        'image_url': image_url,
        'categories': [{'id': c.id, 'name': c.name} for c in product.categories.all()],
        'physical_stock': calculate_physical_stock_level(product),
        'virtual_stock': calculate_virtual_stock_level(product),
    }


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


@require_GET
@require_authenticated_staff_or_superuser
def api_admin_price_lists(request):
    price_lists = PriceList.objects.prefetch_related('prices__product__images').all()
    payload = {
        'price_lists': [_price_list_to_dict(request, price_list) for price_list in price_lists],
    }
    return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


@require_GET
@require_authenticated_staff_or_superuser
def api_admin_products(request):
    products = Product.objects.filter(is_active=True).prefetch_related('images', 'categories').order_by('id')
    categories = ProductCategory.objects.all().order_by('name')
    return JsonResponse(
        {
            'products': [_admin_product_to_dict(request, product) for product in products],
            'categories': [{'id': c.id, 'name': c.name} for c in categories],
        },
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_admin_add_product(request):
    name = (request.POST.get('name') or '').strip()
    if not name:
        return JsonResponse({'detail': 'name is required'}, status=400)

    product = Product.objects.create(
        name=name,
        description=(request.POST.get('description') or '').strip(),
        vat=request.POST.get('vat') or 23,
        ean=(request.POST.get('ean') or '').strip() or None,
        volume_value=request.POST.get('volume_value') or 1,
        volume_unit=request.POST.get('volume_unit') or 'pcs',
    )

    category_ids = request.POST.getlist('categories')
    if category_ids:
        product.categories.set(category_ids)

    if 'image' in request.FILES:
        ProductImage.objects.create(product=product, image=request.FILES['image'])

    for price_list in PriceList.objects.all():
        Price.objects.create(
            price_list=price_list,
            product=product,
            net_price=0,
            gross_price=0,
        )

    product = Product.objects.prefetch_related('images', 'categories').get(pk=product.pk)
    return JsonResponse(
        {'status': 'success', 'product': _admin_product_to_dict(request, product)},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_admin_edit_product(request, product_id):
    product = get_object_or_404(Product.objects.prefetch_related('images', 'categories'), id=product_id)

    name = (request.POST.get('name') or '').strip()
    if not name:
        return JsonResponse({'detail': 'name is required'}, status=400)

    product.name = name
    product.description = (request.POST.get('description') or '').strip()
    product.vat = request.POST.get('vat') or product.vat
    product.ean = (request.POST.get('ean') or '').strip() or None
    product.volume_value = request.POST.get('volume_value') or product.volume_value
    product.volume_unit = request.POST.get('volume_unit') or product.volume_unit

    category_ids = request.POST.getlist('categories')
    product.categories.set(category_ids)

    if 'image' in request.FILES:
        product.images.all().delete()
        ProductImage.objects.create(product=product, image=request.FILES['image'])

    product.save()
    product = Product.objects.prefetch_related('images', 'categories').get(pk=product.pk)
    return JsonResponse(
        {'status': 'success', 'product': _admin_product_to_dict(request, product)},
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_admin_delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return JsonResponse({'status': 'success'})


@require_POST
@require_authenticated_staff_or_superuser
def api_admin_add_product_category(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'detail': 'name is required'}, status=400)

    category, created = ProductCategory.objects.get_or_create(name=name)
    return JsonResponse(
        {
            'status': 'success',
            'created': created,
            'category': {'id': category.id, 'name': category.name},
        },
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_add_price_list(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'detail': 'Name is required'}, status=400)

    price_list = PriceList.objects.create(name=name)
    products = Product.objects.filter(is_active=True)
    for product in products:
        Price.objects.create(
            price_list=price_list,
            product=product,
            net_price=0,
            gross_price=0,
        )

    price_list = PriceList.objects.prefetch_related('prices__product__images').get(pk=price_list.pk)
    return JsonResponse(
        {
            'status': 'success',
            'price_list': _price_list_to_dict(request, price_list),
        },
        json_dumps_params={'ensure_ascii': False},
    )


@require_POST
@require_authenticated_staff_or_superuser
def api_save_price(request):
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    price_list_id = data.get('price_list_id')
    product_id = data.get('product_id')
    net_price = data.get('net_price')
    gross_price = data.get('gross_price')

    if not all([price_list_id, product_id]):
        return JsonResponse({'detail': 'price_list_id and product_id are required'}, status=400)

    if net_price in (None, '') or gross_price in (None, ''):
        return JsonResponse({'detail': 'net_price and gross_price are required'}, status=400)

    try:
        price = Price.objects.get(price_list_id=price_list_id, product_id=product_id)
        price.net_price = net_price
        price.gross_price = gross_price
        price.save()
    except Price.DoesNotExist:
        return JsonResponse({'detail': 'Price not found'}, status=404)
    except Exception as e:
        return JsonResponse({'detail': str(e)}, status=500)

    return JsonResponse({
        'status': 'success',
        'price': {
            'price_list_id': int(price_list_id),
            'product_id': int(product_id),
            'net_price': str(price.net_price),
            'gross_price': str(price.gross_price),
        },
    })


@require_GET
def api_products_list(request):
    """
    API dla zewnętrznego frontendu (np. React).
    Wywołanie z credentials: 'include' – sesja (cookie) identyfikuje użytkownika.
    Wymaga autentykacji i parametru buyer_id.
    - Brak buyer_id: 400 "Nie wybrano kupującego"
    - Kupujący bez przypisanego cennika: 400 "Kupujący nie ma przypisanego cennika"
    - W przeciwnym razie: lista produktów z cenami (dla cennika przypisanego kupującemu).
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    buyer_id = (request.GET.get('buyer_id') or '').strip()
    if not buyer_id:
        return JsonResponse({'detail': 'Nie wybrano kupującego'}, status=400)

    buyer, err = _get_validated_buyer(request, buyer_id)
    if err:
        return err

    User = get_user_model()
    effective_user = User.objects.select_related('profile', 'profile__price_list').get(pk=buyer.id)

    try:
        profile = effective_user.profile
    except Exception:
        profile = None
    price_list = None
    if profile and getattr(profile, 'price_list_id', None):
        price_list = profile.price_list

    if not price_list:
        return JsonResponse({'detail': 'Kupujący nie ma przypisanego cennika'}, status=400)

    products = Product.objects.filter(is_active=True).prefetch_related(
        'images', 'prices__price_list', 'categories'
    )
    prices = Price.objects.filter(
        price_list=price_list,
        product__in=products
    ).values('product_id', 'gross_price')
    product_prices = {p['product_id']: p['gross_price'] for p in prices}

    product_list = []
    for product in products:
        first_image = product.images.first()
        image_url = None
        if first_image and first_image.image:
            image_url = request.build_absolute_uri(first_image.image.url)
        gross_price = product_prices.get(product.id)
        product_list.append({
            'id': product.id,
            'name': product.name,
            'description': product.description or '',
            'image_url': image_url,
            'categories': [{'id': c.id, 'name': c.name} for c in product.categories.all()],
            'volume_value': float(product.volume_value),
            'volume_unit': product.volume_unit,
            'volume_unit_display': product.get_volume_unit_display(),
            'ean': product.ean or None,
            'gross_price': float(gross_price) if gross_price is not None else None,
        })

    if effective_user:
        profile = getattr(effective_user, 'profile', None)
        display_name = (profile.name if profile and getattr(profile, 'name', None) else None) or effective_user.username
        user_payload = {
            'id': effective_user.id,
            'username': effective_user.username,
            'display_name': display_name,
        }
    else:
        user_payload = None

    payload = {
        'products': product_list,
        'price_list': {'id': price_list.id, 'name': price_list.name} if price_list else None,
        'user': user_payload,
    }
    return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


def _build_cart_payload(request, cart):
    """Buduje słownik { cart_items, cart_total } w formacie API koszyka."""
    items_data = []
    cart_total = '0.00'
    if cart:
        for item in cart.items.all():
            first_image = item.product.images.first()
            image_url = None
            if first_image and first_image.image:
                image_url = request.build_absolute_uri(first_image.image.url)
            items_data.append({
                'id': item.id,
                'product_id': item.product.id,
                'product_name': item.product.name,
                'price': str(item.price),
                'quantity': item.quantity,
                'subtotal': str(item.subtotal),
                'image_url': image_url,
            })
        cart_total = str(cart.total_cost)
    return {'cart_items': items_data, 'cart_total': cart_total}


def _get_validated_buyer(request, buyer_id_param):
    """
    Waliduje buyer_id: zwraca (User, None) lub (None, JsonResponse).
    buyer_id_param może być string lub int.
    """
    if buyer_id_param is None or str(buyer_id_param).strip() == '':
        return None, JsonResponse({'detail': 'buyer_id is required'}, status=400)
    User = get_user_model()
    try:
        buyer = User.objects.get(pk=buyer_id_param)
    except (User.DoesNotExist, ValueError):
        return None, JsonResponse({'detail': 'Invalid buyer_id'}, status=400)
    if not (request.user.is_staff or request.user.is_superuser) and str(request.user.id) != str(buyer_id_param):
        return None, JsonResponse({'detail': 'Forbidden'}, status=403)
    return buyer, None


def api_get_cart_items(request):
    """
    API dla zewnętrznego frontendu (np. React) – lista pozycji koszyka.
    Wywołanie z credentials: 'include' (sesja/cookie).
    GET /api/cart/items/?buyer_id=<id>
    - Zalogowany: zwraca pozycje koszyka dla podanego kupującego (buyer_id).
    - Staff/superuser: może podać dowolny buyer_id (koszyk prowadzony przez request.user dla tego kupującego).
    - Nie-staff: buyer_id musi być id zalogowanego użytkownika (własny koszyk).
    - Brak buyer_id: 400.
    Zwraca: { "cart_items": [...], "cart_total": "123.45" } lub pusty koszyk.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    buyer_id = (request.GET.get('buyer_id') or '').strip()
    buyer, err = _get_validated_buyer(request, buyer_id)
    if err:
        return err

    cart = Cart.objects.filter(user=request.user, buyer=buyer).prefetch_related('items__product', 'items__product__images').first()
    payload = _build_cart_payload(request, cart)
    return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


@csrf_exempt
def api_add_cart_item(request):
    """
    API: dodanie lub zmiana ilości produktu w koszyku.
    POST /api/cart/items/
    Body JSON: { "buyer_id": <id>, "product_id": <id>, "quantity": <int> }
    quantity – delta (dodatnia = dodaj, ujemna = odejmij). Np. quantity: 1 dodaje 1 szt., quantity: -1 odejmuje 1.
    Po aktualizacji zwraca pełny stan koszyka: { "cart_items": [...], "cart_total": "..." } (jak GET /api/cart/items/).
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    buyer_id = body.get('buyer_id')
    product_id = body.get('product_id')
    quantity = body.get('quantity', 1)
    buyer, err = _get_validated_buyer(request, buyer_id)
    if err:
        return err

    if product_id is None:
        return JsonResponse({'detail': 'product_id is required'}, status=400)
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'quantity must be an integer'}, status=400)

    try:
        product = Product.objects.get(pk=product_id)
    except (Product.DoesNotExist, ValueError):
        return JsonResponse({'detail': 'Product not found'}, status=404)

    price_list = getattr(buyer, 'profile', None) and getattr(buyer.profile, 'price_list', None)
    if not price_list:
        return JsonResponse({'detail': 'Brak cennika dla kupującego'}, status=400)
    try:
        price_obj = Price.objects.get(price_list=price_list, product=product)
    except Price.DoesNotExist:
        return JsonResponse({'detail': 'Brak ceny dla tego produktu'}, status=400)

    cart, _ = Cart.objects.get_or_create(user=request.user, buyer=buyer)
    cart_item = CartItem.objects.filter(cart=cart, product=product).first()

    if cart_item:
        cart_item.quantity += quantity
        if cart_item.quantity > 0:
            cart_item.save()
        else:
            cart_item.delete()
    else:
        if quantity <= 0:
            return JsonResponse(_build_cart_payload(request, cart), json_dumps_params={'ensure_ascii': False})
        CartItem.objects.create(cart=cart, product=product, quantity=quantity, price=price_obj.gross_price)

    # Odśwież koszyk (np. po delete pozycji)
    cart = Cart.objects.filter(user=request.user, buyer=buyer).prefetch_related('items__product', 'items__product__images').first()
    payload = _build_cart_payload(request, cart)
    return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


@csrf_exempt
def api_remove_cart_item(request):
    """
    API: usunięcie produktu z koszyka (całkowite usunięcie pozycji).
    DELETE /api/cart/items/?buyer_id=<id>&product_id=<id>
    Zwraca pełny stan koszyka po usunięciu: { "cart_items": [...], "cart_total": "..." }.
    """
    if request.method != 'DELETE':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    buyer_id = (request.GET.get('buyer_id') or '').strip()
    product_id = request.GET.get('product_id')
    buyer, err = _get_validated_buyer(request, buyer_id)
    if err:
        return err

    if product_id is None or str(product_id).strip() == '':
        return JsonResponse({'detail': 'product_id is required'}, status=400)

    try:
        cart = Cart.objects.get(user=request.user, buyer=buyer)
        CartItem.objects.filter(cart=cart, product_id=product_id).delete()
    except Cart.DoesNotExist:
        pass

    cart = Cart.objects.filter(user=request.user, buyer=buyer).prefetch_related('items__product', 'items__product__images').first()
    payload = _build_cart_payload(request, cart)
    return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


def modify_cart_item_quantity_by(cart, product_id, quantity, operation):
    """
    Modyfikuje ilość sztuk produktu w koszyku.
    operation: "decrease" – zmniejsza o quantity; "increase" – zwiększa o quantity.
    quantity – dodatnia liczba (delta).
    Zwraca: nowa liczba sztuk (int) lub None, gdy pozycja nie istnieje w koszyku.
    """
    cart_item = CartItem.objects.filter(cart=cart, product_id=product_id).first()
    if not cart_item:
        return None

    if operation == 'decrease':
        new_quantity = max(0, cart_item.quantity - quantity)
        if new_quantity == 0:
            cart_item.delete()
        else:
            cart_item.quantity = new_quantity
            cart_item.save()
        return new_quantity
    elif operation == 'increase':
        cart_item.quantity += quantity
        cart_item.save()
        return cart_item.quantity
    else:
        raise ValueError(f'Invalid operation: {operation}')


def _parse_decrease_increase_body(request):
    """
    Wspólna walidacja body dla api_decrease_cart_item_quantity i api_increase_cart_item_quantity.
    Zwraca (buyer, product_id, quantity) lub (None, JsonResponse).
    """
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return None, JsonResponse({'detail': 'Invalid JSON'}, status=400)

    buyer_id = body.get('buyer_id')
    if buyer_id is None or str(buyer_id).strip() == '':
        return None, JsonResponse({'detail': 'Nie podano buyer_id'}, status=400)

    buyer, err = _get_validated_buyer(request, buyer_id)
    if err:
        return None, err

    product_id = body.get('product_id')
    if product_id is None:
        return None, JsonResponse({'detail': 'product_id is required'}, status=400)

    quantity = body.get('quantity')
    if quantity is None:
        return None, JsonResponse({'detail': 'quantity is required'}, status=400)
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return None, JsonResponse({'detail': 'quantity must be a positive integer'}, status=400)
    if quantity <= 0:
        return None, JsonResponse({'detail': 'quantity must be a positive integer'}, status=400)

    return (buyer, product_id, quantity), None


@csrf_exempt
def api_decrease_cart_item_quantity(request):
    """
    API: zmniejszenie liczby sztuk produktu w koszyku o podaną wartość.
    POST /api/cart/items/decrease/
    Body JSON: { "buyer_id": <id>, "product_id": <id>, "quantity": <int> }
    quantity – o ile sztuk zmniejszyć (dodatnia liczba).
    Zwraca: { "product_id": <id>, "quantity": <int> } – nowa liczba sztuk po zmniejszeniu (0 jeśli pozycja usunięta).
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    parsed, err = _parse_decrease_increase_body(request)
    if err:
        return err
    buyer, product_id, quantity = parsed

    try:
        cart = Cart.objects.get(user=request.user, buyer=buyer)
    except Cart.DoesNotExist:
        return JsonResponse({'detail': 'Koszyk nie istnieje'}, status=404)

    new_quantity = modify_cart_item_quantity_by(cart, product_id, quantity, operation='decrease')
    if new_quantity is None:
        return JsonResponse({'detail': 'Produkt nie jest w koszyku'}, status=404)

    return JsonResponse(
        {'product_id': int(product_id), 'quantity': new_quantity},
        json_dumps_params={'ensure_ascii': False},
    )


@csrf_exempt
def api_increase_cart_item_quantity(request):
    """
    API: zwiększenie liczby sztuk produktu w koszyku o podaną wartość.
    POST /api/cart/items/increase/
    Body JSON: { "buyer_id": <id>, "product_id": <id>, "quantity": <int> }
    quantity – o ile sztuk zwiększyć (dodatnia liczba).
    Zwraca: { "product_id": <id>, "quantity": <int> } – nowa liczba sztuk po zwiększeniu.
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    parsed, err = _parse_decrease_increase_body(request)
    if err:
        return err
    buyer, product_id, quantity = parsed

    try:
        cart = Cart.objects.get(user=request.user, buyer=buyer)
    except Cart.DoesNotExist:
        return JsonResponse({'detail': 'Koszyk nie istnieje'}, status=404)

    new_quantity = modify_cart_item_quantity_by(cart, product_id, quantity, operation='increase')
    if new_quantity is None:
        return JsonResponse({'detail': 'Produkt nie jest w koszyku'}, status=404)

    return JsonResponse(
        {'product_id': int(product_id), 'quantity': new_quantity},
        json_dumps_params={'ensure_ascii': False},
    )


def api_cart_items(request):
    """
    Dyspozytor dla /api/cart/items/: GET – lista, POST – dodaj/zmień ilość, DELETE – usuń pozycję.
    """
    if request.method == 'GET':
        return api_get_cart_items(request)
    if request.method == 'POST':
        return api_add_cart_item(request)
    if request.method == 'DELETE':
        return api_remove_cart_item(request)
    return JsonResponse({'detail': 'Method not allowed'}, status=405)


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

@require_GET
def api_buyers_list(request):
    """
    Lista kupujących (beneficjentów) do dropdownu dla staff.
    Tylko dla zalogowanych staff/superuser. Zwraca id, display_name (profile.name lub username).
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'detail': 'Staff required'}, status=403)
    User = get_user_model()
    beneficiaries = User.objects.filter(profile__is_beneficiary=True).select_related('profile')
    buyers = []
    for u in beneficiaries:
        profile = getattr(u, 'profile', None)
        display_name = (profile.name if profile and getattr(profile, 'name', None) else None) or u.username
        buyers.append({'id': u.id, 'username': u.username, 'display_name': display_name})
    return JsonResponse({'buyers': buyers}, json_dumps_params={'ensure_ascii': False})


@csrf_exempt
def api_cart_change_buyer(request):
    """
    POST /api/cart/change-buyer/ – ustawia w sesji wybranego kupującego (selected_buyer_id).
    Body JSON: { "buyer_id": <id> }. Tylko staff. Front wywołuje przed dodaniem do koszyka.
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'detail': 'Staff required'}, status=403)
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)
    buyer_id = body.get('buyer_id')
    if buyer_id is not None:
        User = get_user_model()
        try:
            buyer = User.objects.get(pk=buyer_id)
            request.session['selected_buyer_id'] = int(buyer_id)
            profile = getattr(buyer, 'profile', None)
            display_name = (profile.name if profile and getattr(profile, 'name', None) else None) or buyer.username
            return JsonResponse({
                'status': 'success',
                'user': {'id': buyer.id, 'username': buyer.username, 'display_name': display_name},
            }, json_dumps_params={'ensure_ascii': False})
        except (User.DoesNotExist, ValueError):
            return JsonResponse({'detail': 'Invalid buyer_id'}, status=400)
    request.session.pop('selected_buyer_id', None)
    return JsonResponse({'status': 'success', 'user': None})


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
        _delete_order_impl(order_id)
        return JsonResponse({'status': 'success', 'message': 'Zamówienie zostało usunięte'})
    except Order.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Zamówienie nie zostało znalezione'
        }, status=404)


def _delete_order_impl(order_id):
    """
    Bezpieczne kasowanie Order zgodne z ORDER_DELETE_PROMPT.md:
    - najpierw finanse: jawne usunięcie SettlementAllocation dla pozycji, odpięcie M2M Payment ↔ pozycje
      (pozostałe CASCADE przy kasowaniu OrderItem); Payment.related_order → SET_NULL przy usunięciu Order,
    - potem usunięcie StockReduction (żeby PROTECT nie blokował),
    - następnie rekalkulacja StockEntry.remaining_quantity,
    - na końcu CASCADE delete Order (OrderItem).
    """
    with transaction.atomic():
        order = Order.objects.select_related('buyer').get(id=order_id)
        order_items = list(order.items.all())

        # Prepare stock reductions + affected stock entry ids
        stock_reductions_qs = StockReduction.objects.filter(order=order)
        affected_stock_entry_ids = list(
            stock_reductions_qs
            .exclude(stock_entry__isnull=True)
            .values_list('stock_entry_id', flat=True)
            .distinct()
        )

        if order_items:
            item_ids = [oi.id for oi in order_items]
            SettlementAllocation.objects.filter(order_item_id__in=item_ids).delete()

            payments_qs = Payment.objects.filter(related_order_items__in=order_items).distinct()
            for payment in payments_qs:
                payment.related_order_items.remove(*order_items)

        # Delete stock reductions before deleting Order/OrderItem (PROTECT)
        stock_reductions_qs.delete()

        # Recalculate StockEntry.remaining_quantity from current StockReduction state
        if affected_stock_entry_ids:
            used_by_entry_id = {}
            for row in (
                StockReduction.objects
                .filter(stock_entry_id__in=affected_stock_entry_ids)
                .values('stock_entry_id')
                .annotate(used=Sum('quantity'))
            ):
                used_by_entry_id[row['stock_entry_id']] = row['used']

            for entry in StockEntry.objects.filter(id__in=affected_stock_entry_ids):
                used = used_by_entry_id.get(entry.id, 0) or 0
                new_remaining = max(entry.quantity - used, 0)
                entry.remaining_quantity = new_remaining
                entry.save(update_fields=['remaining_quantity'])

        # Finally delete Order (CASCADE deletes OrderItem)
        order.delete()


@require_POST
@require_authenticated_staff_or_superuser
def api_delete_order(request, order_id):
    try:
        _delete_order_impl(order_id)
        return JsonResponse({'status': 'success', 'message': 'Zamówienie zostało usunięte'})
    except Order.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Zamówienie nie zostało znalezione'}, status=404)

@csrf_exempt
def api_create_order(request):
    """
    API: składa zamówienie z koszyka dla podanego kupującego.
    POST /api/cart/order/
    Body JSON: { "buyer_id": <id>, "max_payable_amount": "..." }
    - Staff/superuser: może złożyć zamówienie dla dowolnego kupującego.
    - Zalogowany użytkownik: może złożyć zamówienie tylko dla siebie.
    Pozycje są kopiowane bezpośrednio z koszyka – dofinansowanie przypisywane jest ręcznie po złożeniu zamówienia.
    Zwraca 201: { "order_id": <id>, "total_cost": "...", "status": "...", "items": [...] }
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    buyer_id = body.get('buyer_id')
    buyer, err = _get_validated_buyer(request, buyer_id)
    if err:
        return err

    try:
        cart = Cart.objects.prefetch_related('items__product').get(user=request.user, buyer=buyer)
    except Cart.DoesNotExist:
        return JsonResponse({'detail': 'Koszyk nie istnieje'}, status=404)

    if not cart.items.exists():
        return JsonResponse({'detail': 'Koszyk jest pusty'}, status=400)

    raw_max_payable_amount = body.get('max_payable_amount', cart.total_cost)
    try:
        max_payable_amount = Decimal(str(raw_max_payable_amount))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({'detail': 'Nieprawidłowa wartość max_payable_amount'}, status=400)

    if max_payable_amount < 0:
        return JsonResponse({'detail': 'max_payable_amount nie może być ujemne'}, status=400)
    if max_payable_amount > cart.total_cost:
        return JsonResponse({'detail': 'max_payable_amount nie może być większe niż total_cost'}, status=400)

    from .cart_create_order import create_stock_reductions

    order = Order.objects.create(
        user=request.user,
        buyer=buyer,
        total_cost=cart.total_cost,
        max_payable_amount=max_payable_amount,
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

    items_data = [
        {
            'id': oi.id,
            'product_id': oi.product_id,
            'product_name': oi.product.name,
            'price': str(oi.price),
            'buyer_id': oi.buyer_id,
        }
        for oi in order.items.select_related('product').all()
    ]

    return JsonResponse({
        'order_id': order.id,
        'total_cost': str(order.total_cost),
        'max_payable_amount': str(order.max_payable_amount) if order.max_payable_amount is not None else None,
        'status': order.status,
        'payment_status': order.payment_status,
        'items': items_data,
    }, status=201, json_dumps_params={'ensure_ascii': False})


def api_list_of_orders_for_buyer(request):
    """
    API: lista zamówień dla podanego kupującego.
    GET /api/orders/?buyer_id=<id>
    - Staff/superuser: może pobrać zamówienia dla dowolnego kupującego.
    - Zalogowany użytkownik: może pobrać wyłącznie własne zamówienia.
    Zwraca 200: { "orders": [...] }
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    buyer_id = (request.GET.get('buyer_id') or '').strip()
    buyer, err = _get_validated_buyer(request, buyer_id)
    if err:
        return err

    orders = (
        Order.objects
        .filter(buyer=buyer)
        .select_related('buyer')
        .prefetch_related('items__product__images')
        .order_by('-created_at')
    )

    orders_data = []
    for order in orders:
        items_data = []
        left_to_pay_buyer = 0
        for item in order.items.select_related('buyer').all():
            first_image = item.product.images.first()
            image_url = request.build_absolute_uri(first_image.image.url) if first_image and first_image.image else None
            items_data.append({
                'id': item.id,
                'product_id': item.product_id,
                'product_name': item.product.name,
                'image_url': image_url,
                'price': str(item.price),
                'buyer_id': item.buyer_id,
                'buyer_name': item.buyer.get_organization_name_or_full_name() or item.buyer.username if item.buyer else None,
                'left_to_pay': str(item.left_to_pay),
            })
            if item.buyer_id == buyer.id:
                left_to_pay_buyer += item.left_to_pay
        orders_data.append({
            'id': order.id,
            'status': order.status,
            'payment_status': order.payment_status,
            'created_at': order.created_at.isoformat(),
            'total_cost': str(order.total_cost),
            'max_payable_amount': str(order.max_payable_amount) if order.max_payable_amount is not None else None,
            'left_to_pay_buyer': str(left_to_pay_buyer),
            'buyer_id': order.buyer_id,
            'buyer_name': order.buyer.get_organization_name_or_full_name() or order.buyer.username,
            'items': items_data,
        })

    return JsonResponse({'orders': orders_data}, json_dumps_params={'ensure_ascii': False})


def api_list_of_orders_for_admin(request):
    """
    API: lista wszystkich zamówień (tylko dla admina/staff).
    GET /api/admin/orders/
    - Staff/superuser: pobiera wszystkie zamówienia w systemie.
    Zwraca 200: { "orders": [...] }
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'detail': 'Permission denied'}, status=403)

    orders = (
        Order.objects
        .select_related('buyer')
        .prefetch_related('items__product__images')
        .order_by('-created_at')
    )

    orders_data = []
    for order in orders:
        items_data = []
        for item in order.items.select_related('buyer').all():
            first_image = item.product.images.first()
            image_url = request.build_absolute_uri(first_image.image.url) if first_image and first_image.image else None
            items_data.append({
                'id': item.id,
                'product_id': item.product_id,
                'product_name': item.product.name,
                'image_url': image_url,
                'price': str(item.price),
                'buyer_id': item.buyer_id,
                'buyer_name': item.buyer.get_organization_name_or_full_name() or item.buyer.username if item.buyer else None,
                'left_to_pay': str(item.left_to_pay),
            })
        orders_data.append({
            'id': order.id,
            'status': order.status,
            'payment_status': order.payment_status,
            'created_at': order.created_at.isoformat(),
            'total_cost': str(order.total_cost),
            'max_payable_amount': str(order.max_payable_amount) if order.max_payable_amount is not None else None,
            'buyer_id': order.buyer_id,
            'buyer_name': order.buyer.get_organization_name_or_full_name() or order.buyer.username,
            'items': items_data,
        })

    return JsonResponse({'orders': orders_data}, json_dumps_params={'ensure_ascii': False})


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

