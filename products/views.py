from .models import Product, ProductImage
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from domy.decorators import require_authenticated_staff_or_superuser
from django.shortcuts import get_object_or_404, redirect, render

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
