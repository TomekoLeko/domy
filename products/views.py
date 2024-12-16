from django.shortcuts import render
from .models import Product
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from domy.decorators import require_authenticated_staff_or_superuser

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
