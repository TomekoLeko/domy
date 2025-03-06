from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Payment, Invoice
from products.models import Order
from .forms import PaymentForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
import json
from datetime import datetime, date
import calendar
from django.db.models import Count, Q
from domy.decorators import require_authenticated_staff_or_superuser
from decimal import Decimal
from .models import Supplier

User = get_user_model()

@staff_member_required
def finance_main(request):
    payments = Payment.objects.all().select_related('related_user', 'created_by')[:50]
    form = PaymentForm()

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.created_by = request.user
            payment.save()
            messages.success(request, 'Płatność została dodana pomyślnie.')
            return redirect('finance:main')

    context = {
        'payments': payments,
        'form': form,
    }
    return render(request, 'finance/main.html', context)

@require_POST
@staff_member_required
def delete_payment(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.delete()
    return JsonResponse({'status': 'success'})

@staff_member_required
def add_multiple_transfers(request):
    all_payments = Payment.objects.all().values('payment_date', 'amount', 'description')
    
    payment_types = [{'value': value, 'label': label} for value, label in Payment.PAYMENT_TYPES]
    payment_types_json = json.dumps(payment_types)

    context = {
        'payment_types': payment_types_json,
        'all_payments': json.dumps(list(all_payments), cls=DjangoJSONEncoder)
    }
    return render(request, 'finance/add_multiple_transfers.html', context)

@staff_member_required
def get_filtered_users(request):
    payment_type = request.GET.get('payment_type')
    users = User.objects.filter(is_active=True).select_related('profile')

    if payment_type == 'contribution':
        users = users.filter(profile__is_contributor=True)
    elif payment_type == 'order_payment':
        users = users.filter(profile__is_beneficiary=True)

    return JsonResponse({
        'users': [
            {
                'id': user.id,
                'name': user.profile.name if hasattr(user, 'profile') and user.profile.name else user.username
            }
            for user in users
        ]
    })

@staff_member_required
def get_filtered_orders(request):
    user_id = request.GET.get('user_id')
    orders = []

    if user_id:
        orders = Order.objects.filter(buyer_id=user_id).order_by('-created_at')

    return JsonResponse({
        'orders': [
            {
                'id': order.id,
                'display': f'Zamówienie z {order.created_at.strftime("%d.m.%Y %H:%M")} ({order.total_cost} zł)'
            }
            for order in orders
        ]
    })

@require_POST
@staff_member_required
def save_multiple_payments(request):
    try:
        data = json.loads(request.body)
        payments = data.get('payments', [])

        for payment_data in payments:
            Payment.objects.create(
                payment_date=payment_data['date'],
                payment_type=payment_data['type'] or 'other',
                amount=payment_data['amount'],
                sender=payment_data['sender'],
                description=payment_data['description'],
                related_user=None,
                created_by=request.user
            )

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
def finance_report(request):
    current_year = date.today().year
    years = range(current_year - 4, current_year + 1)

    return render(request, 'finance/report.html', {'years': years})

@require_POST
@staff_member_required
def delete_all_payments(request):
    try:
        Payment.objects.all().delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
def get_report_data(request):
    month = int(request.GET.get('month', date.today().month))
    year = int(request.GET.get('year', date.today().year))

    # Get the first and last day of the selected month
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    payments = Payment.objects.filter(
        payment_date__gte=first_day,
        payment_date__lte=last_day
    ).exclude(
        payment_type='invoice'
    ).order_by('payment_date')

    return JsonResponse({
        'payments': [{
            'payment_date': payment.payment_date.strftime('%d.%m.%Y'),
            'description': payment.description,
            'sender': payment.sender,
            'amount': float(payment.amount)
        } for payment in payments]
    })

@require_authenticated_staff_or_superuser
def invoices(request):
    # Get sort parameter
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by not in ['invoice_number', 'supplier_name', 'net_price', 'gross_price', 'created_at',
                      '-invoice_number', '-supplier_name', '-net_price', '-gross_price', '-created_at']:
        sort_by = '-created_at'

    # Get search query
    search_query = request.GET.get('search', '')

    # Filter and sort invoices
    invoices = Invoice.objects.annotate(
        supply_orders_count=Count('supply_orders')
    )

    if search_query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search_query) |
            Q(supplier_name__icontains=search_query)
        )

    invoices = invoices.order_by(sort_by)

    suppliers = Supplier.objects.all()
    
    return render(request, 'finance/invoices.html', {
        'invoices': invoices,
        'current_sort': sort_by,
        'search_query': search_query,
        'suppliers': suppliers
    })

@require_POST
@require_authenticated_staff_or_superuser
def add_invoice(request):
    try:
        supplier = get_object_or_404(Supplier, id=request.POST.get('supplier'))
        invoice_number = request.POST.get('invoice_number')
        net_price = Decimal(request.POST.get('net_price'))
        vat_rate = Decimal(request.POST.get('vat_rate'))
        gross_price = Decimal(request.POST.get('gross_price'))

        if Invoice.objects.filter(invoice_number=invoice_number).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'Faktura o tym numerze już istnieje'
            }, status=400)

        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            supplier=supplier,
            net_price=net_price,
            vat_rate=vat_rate,
            gross_price=gross_price
        )

        return JsonResponse({
            'status': 'success',
            'invoice_id': invoice.id
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
