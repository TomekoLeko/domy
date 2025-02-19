from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Payment
from products.models import Order
from .forms import PaymentForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
import json

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
    payment_types = [{'value': value, 'label': label} for value, label in Payment.PAYMENT_TYPES]
    payment_types_json = json.dumps(payment_types)
    return render(request, 'finance/add_multiple_transfers.html', {'payment_types': payment_types_json})

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
                payment_type=payment_data['type'] or 'other',  # Default to 'other' if type is empty
                amount=payment_data['amount'],
                description=payment_data['description'],
                related_user=None,  # For now, we're not handling user relations
                created_by=request.user
            )

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
def finance_report(request):
    return render(request, 'finance/report.html')
