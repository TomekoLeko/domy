from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from domy.decorators import require_authenticated_staff_or_superuser
from .models import Supplier

@require_authenticated_staff_or_superuser
def suppliers(request):
    suppliers = Supplier.objects.all().order_by('-created_at')
    return render(request, 'stock/suppliers.html', {
        'suppliers': suppliers
    })

@require_POST
@require_authenticated_staff_or_superuser
def add_supplier(request):
    name = request.POST.get('name')
    address = request.POST.get('address')
    postal = request.POST.get('postal')
    city = request.POST.get('city')
    mail = request.POST.get('mail')
    phone = request.POST.get('phone')
    nip = request.POST.get('nip')

    if name:
        supplier = Supplier.objects.create(
            name=name,
            address=address,
            postal=postal,
            city=city,
            mail=mail,
            phone=phone,
            nip=nip
        )
        return JsonResponse({
            'status': 'success',
            'supplier_id': supplier.id,
            'name': supplier.name
        })
    return JsonResponse({'status': 'error', 'message': 'Name is required'}, status=400)

@require_POST
@require_authenticated_staff_or_superuser
def edit_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)
    
    supplier.name = request.POST.get('name', supplier.name)
    supplier.address = request.POST.get('address', supplier.address)
    supplier.postal = request.POST.get('postal', supplier.postal)
    supplier.city = request.POST.get('city', supplier.city)
    supplier.mail = request.POST.get('mail', supplier.mail)
    supplier.phone = request.POST.get('phone', supplier.phone)
    supplier.nip = request.POST.get('nip', supplier.nip)
    
    supplier.save()
    return JsonResponse({'status': 'success'})

@require_POST
@require_authenticated_staff_or_superuser
def delete_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)
    supplier.delete()
    return JsonResponse({'status': 'success'}) 
