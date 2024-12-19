from .models import Product, ProductImage, PriceList, Price
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from domy.decorators import require_authenticated_staff_or_superuser
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
import json

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
