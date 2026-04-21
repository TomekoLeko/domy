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
from django.db import transaction
from domy.decorators import require_authenticated_staff_or_superuser
from decimal import Decimal, InvalidOperation
from .models import Supplier
from finance.models import Payment
from products.models import OrderItem

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
    elif payment_type == 'order':
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
    ).prefetch_related(
        'supply_orders',
        'supply_orders__stock_entries',
        'supply_orders__stock_entries__product'
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
        invoice_number = request.POST.get('invoice_number')
        supplier_id = request.POST.get('supplier')
        gross_price = Decimal(request.POST.get('gross_price'))

        # Validate required fields
        if not all([invoice_number, supplier_id, gross_price]):
            return JsonResponse({
                'status': 'error',
                'message': 'Wszystkie pola są wymagane.'
            })

        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            supplier_id=supplier_id,
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

@require_POST
@require_authenticated_staff_or_superuser
def delete_invoice(request, invoice_id):
    try:
        invoice = get_object_or_404(Invoice, id=invoice_id)
        
        # If there are associated supply orders, clear the invoice reference
        for supply_order in invoice.supply_orders.all():
            supply_order.invoice = None
            supply_order.save()
        
        # Then delete the invoice
        invoice.delete()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

def contributions(request):
    """View for listing all contributors with their related payments"""
    User = get_user_model()

    contributors = User.objects.filter(
        profile__is_contributor=True
    ).prefetch_related(
        'related_payments',
        'related_payments__related_order_items',
        'related_payments__related_order_items__product'
    )

    return render(request, 'finance/contributions.html', {
        'contributors': contributors
    })

@staff_member_required
def get_user_payments(request, user_id):
    """Get payments related to a specific user"""

    try:
        user = get_object_or_404(User, id=user_id)

        payments = Payment.objects.filter(
            related_user=user
        ).order_by('-payment_date')

        # Combine both querysets
        all_payments = list(payments)
        
        # Convert to JSON-serializable format
        payment_data = [{
            'id': payment.id,
            'payment_date': payment.payment_date.strftime('%d.%m.%Y'),
            'amount': str(payment.amount),
            'sender': payment.sender or '',
            'description': payment.description or ''
        } for payment in all_payments]
        
        return JsonResponse({
            'status': 'success',
            'payments': payment_data
        })
    except Exception as e:
        import traceback
        traceback.print_exc()  # Print traceback to server console for debugging
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@staff_member_required
def get_available_contributions(request):
    """Return all available contribution payments with calculated available amount."""
    payments = Payment.get_available_contributions().select_related(
        'related_user',
        'related_order',
        'created_by'
    ).prefetch_related('related_order_items')

    payment_data = [{
        'id': payment.id,
        'amount': str(payment.amount),
        'payment_type': payment.payment_type,
        'description': payment.description,
        'sender': payment.sender,
        'related_user': payment.related_user_id,
        'related_order': payment.related_order_id,
        'related_order_items': list(payment.related_order_items.values_list('id', flat=True)),
        'created_by': payment.created_by_id,
        'created_at': payment.created_at.isoformat(),
        'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
        'available_amount': str(payment.available_amount),
    } for payment in payments]

    return JsonResponse({
        'status': 'success',
        'payments': payment_data
    })


@staff_member_required
def get_all_contributions(request):
    """Return all contribution payments with full related objects."""
    payments = Payment.objects.filter(payment_type='contribution').select_related(
        'related_user',
        'related_order',
        'created_by'
    ).prefetch_related('related_order_items', 'related_order_items__buyer', 'related_order_items__product__images')

    def serialize_order_item(order_item):
        first_image = order_item.product.images.first()
        return {
            'id': order_item.id,
            'order_id': order_item.order_id,
            'product_id': order_item.product_id,
            'product_name': order_item.product.name,
            'image_url': first_image.image.url if first_image and first_image.image else None,
            'price': str(order_item.price),
            'buyer_id': order_item.buyer_id,
            'buyer_name': (
                order_item.buyer.get_organization_name_or_full_name() or order_item.buyer.username
                if order_item.buyer else None
            ),
        }

    payment_data = [{
        'id': payment.id,
        'amount': str(payment.amount),
        'payment_type': payment.payment_type,
        'description': payment.description,
        'sender': payment.sender,
        'related_user': {
            'id': payment.related_user.id,
            'name': payment.related_user.get_organization_name_or_full_name() or payment.related_user.username,
            'full_name': payment.related_user.get_organization_name_or_full_name(),
        } if payment.related_user else None,
        'related_order': payment.related_order_id,
        'related_order_items': [
            serialize_order_item(order_item) for order_item in payment.related_order_items.all()
        ],
        'created_by': payment.created_by_id,
        'created_at': payment.created_at.isoformat(),
        'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
        'available_amount': str(payment.available_amount),
    } for payment in payments]

    return JsonResponse({
        'status': 'success',
        'payments': payment_data
    })

@staff_member_required
def api_get_contributors(request):
    """Return active contributors for contribution creation form."""
    contributors = (
        User.objects
        .filter(is_active=True, profile__is_contributor=True)
        .select_related('profile')
        .order_by('profile__name', 'username')
    )

    users = [
        {
            'id': contributor.id,
            'name': contributor.profile.name if hasattr(contributor, 'profile') and contributor.profile.name else contributor.username,
        }
        for contributor in contributors
    ]

    return JsonResponse({'users': users})

@require_POST
@staff_member_required
def assign_payment_to_item(request):
    """Assign a payment to an order item"""
    try:
        data = json.loads(request.body)
        payment_id = data.get('payment_id')
        order_item_id = data.get('order_item_id')
        
        if not payment_id or not order_item_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameters'
            }, status=400)
        
        payment = get_object_or_404(Payment, id=payment_id)
        
        # Use correct import for OrderItem
        from products.models import OrderItem
        order_item = get_object_or_404(OrderItem, id=order_item_id)
        
        # Add the order item to the payment's related items
        payment.related_order_items.add(order_item)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Płatność została przypisana pomyślnie'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()  # Print traceback to server console for debugging
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)


VALID_PAYMENT_TYPE_VALUES = {choice[0] for choice in Payment.PAYMENT_TYPES}


@require_POST
@staff_member_required
def api_assign_contributions_to_order(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse(
            {'status': 'error', 'message': 'Invalid JSON body'},
            status=400,
        )

    order_id = data.get('order_id')
    assignments = data.get('assignments')

    if order_id is None:
        return JsonResponse(
            {'status': 'error', 'message': 'order_id is required'},
            status=400,
        )

    if not isinstance(assignments, list):
        return JsonResponse(
            {'status': 'error', 'message': 'assignments must be a list'},
            status=400,
        )

    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return JsonResponse(
            {'status': 'error', 'message': 'order_id must be an integer'},
            status=400,
        )

    order = get_object_or_404(Order, id=order_id)
    order_items_qs = OrderItem.objects.filter(order=order).select_related('order')
    order_items_by_id = {item.id: item for item in order_items_qs}

    requested_item_to_payment = {}
    requested_item_prices = {}
    requested_payment_ids = set()

    for idx, assignment in enumerate(assignments):
        if not isinstance(assignment, dict):
            return JsonResponse(
                {'status': 'error', 'message': f'assignments[{idx}] must be an object'},
                status=400,
            )

        payment_id = assignment.get('payment_id')
        order_item_ids = assignment.get('order_item_ids') or []
        raw_unit_price = assignment.get('unit_price')

        try:
            payment_id = int(payment_id)
        except (TypeError, ValueError):
            return JsonResponse(
                {'status': 'error', 'message': f'assignments[{idx}].payment_id must be an integer'},
                status=400,
            )

        if not isinstance(order_item_ids, list) or len(order_item_ids) == 0:
            return JsonResponse(
                {'status': 'error', 'message': f'assignments[{idx}].order_item_ids must be a non-empty list'},
                status=400,
            )

        try:
            parsed_price = Decimal(str(raw_unit_price))
        except (InvalidOperation, TypeError, ValueError):
            return JsonResponse(
                {'status': 'error', 'message': f'assignments[{idx}].unit_price must be a valid decimal'},
                status=400,
            )

        if parsed_price < 0:
            return JsonResponse(
                {'status': 'error', 'message': f'assignments[{idx}].unit_price cannot be negative'},
                status=400,
            )

        requested_payment_ids.add(payment_id)

        for raw_order_item_id in order_item_ids:
            try:
                order_item_id = int(raw_order_item_id)
            except (TypeError, ValueError):
                return JsonResponse(
                    {'status': 'error', 'message': f'Invalid order_item_id in assignments[{idx}]'},
                    status=400,
                )

            if order_item_id not in order_items_by_id:
                return JsonResponse(
                    {'status': 'error', 'message': f'Order item {order_item_id} does not belong to order {order.id}'},
                    status=400,
                )

            if order_item_id in requested_item_to_payment:
                return JsonResponse(
                    {'status': 'error', 'message': f'Order item {order_item_id} assigned multiple times'},
                    status=400,
                )

            requested_item_to_payment[order_item_id] = payment_id
            requested_item_prices[order_item_id] = parsed_price

    payments = Payment.objects.filter(
        id__in=requested_payment_ids,
        payment_type='contribution',
    ).prefetch_related('related_order_items')
    payments_by_id = {payment.id: payment for payment in payments}

    missing_payment_ids = sorted(requested_payment_ids - set(payments_by_id.keys()))
    if missing_payment_ids:
        return JsonResponse(
            {
                'status': 'error',
                'message': f'Contribution payments not found: {", ".join(str(pid) for pid in missing_payment_ids)}',
            },
            status=404,
        )

    requested_sum_by_payment = {}
    for order_item_id, payment_id in requested_item_to_payment.items():
        requested_sum_by_payment.setdefault(payment_id, Decimal('0.00'))
        requested_sum_by_payment[payment_id] += requested_item_prices[order_item_id]

    requested_order_item_ids = set(requested_item_to_payment.keys())
    for payment_id, payment in payments_by_id.items():
        used_outside_current_request = sum(
            order_item.price
            for order_item in payment.related_order_items.all()
            if order_item.id not in requested_order_item_ids
        )
        available_for_request = payment.amount - used_outside_current_request
        requested_sum = requested_sum_by_payment.get(payment_id, Decimal('0.00'))
        if requested_sum > available_for_request:
            return JsonResponse(
                {
                    'status': 'error',
                    'message': (
                        f'Payment {payment_id} has insufficient available amount. '
                        f'Available: {available_for_request}, requested: {requested_sum}'
                    ),
                },
                status=400,
            )

    with transaction.atomic():
        # Persist edited item prices and buyer mapping from assigned contribution.
        for order_item_id, unit_price in requested_item_prices.items():
            order_item = order_items_by_id[order_item_id]
            payment_id = requested_item_to_payment[order_item_id]
            payment = payments_by_id[payment_id]

            update_fields = []
            if order_item.price != unit_price:
                order_item.price = unit_price
                update_fields.append('price')
            if order_item.buyer_id != payment.related_user_id:
                order_item.buyer = payment.related_user
                update_fields.append('buyer')

            if update_fields:
                order_item.save(update_fields=update_fields)

        if requested_order_item_ids:
            linked_contributions = Payment.objects.filter(
                payment_type='contribution',
                related_order_items__id__in=requested_order_item_ids,
            ).distinct()
            linked_order_items = list(order_items_qs.filter(id__in=requested_order_item_ids))
            for contribution in linked_contributions:
                contribution.related_order_items.remove(*linked_order_items)

        grouped_item_ids = {}
        for order_item_id, payment_id in requested_item_to_payment.items():
            grouped_item_ids.setdefault(payment_id, [])
            grouped_item_ids[payment_id].append(order_item_id)

        for payment_id, order_item_ids in grouped_item_ids.items():
            payment = payments_by_id[payment_id]
            items_to_add = list(order_items_qs.filter(id__in=order_item_ids))
            payment.related_order_items.add(*items_to_add)

    return JsonResponse(
        {
            'status': 'success',
            'order_id': order.id,
            'assigned_items_count': len(requested_order_item_ids),
            'assigned_payments_count': len(grouped_item_ids),
        }
    )


@require_POST
@staff_member_required
def api_create_payment(request):
    """
    Create a single payment (JSON API for staff UI).
    Requires payment_type; see docs/API_CREATE_PAYMENT.md.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse(
            {'status': 'error', 'message': 'Invalid JSON body'},
            status=400,
        )

    payment_type = data.get('payment_type')
    if payment_type is None or (isinstance(payment_type, str) and not str(payment_type).strip()):
        return JsonResponse(
            {
                'status': 'error',
                'message': 'payment_type is required',
            },
            status=400,
        )

    if payment_type not in VALID_PAYMENT_TYPE_VALUES:
        return JsonResponse(
            {
                'status': 'error',
                'message': 'Invalid payment_type',
                'allowed_payment_types': sorted(VALID_PAYMENT_TYPE_VALUES),
            },
            status=400,
        )

    if 'amount' not in data:
        return JsonResponse(
            {'status': 'error', 'message': 'amount is required'},
            status=400,
        )

    try:
        amount = Decimal(str(data['amount']))
    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse(
            {'status': 'error', 'message': 'amount must be a valid decimal number'},
            status=400,
        )

    if amount <= 0:
        return JsonResponse(
            {'status': 'error', 'message': 'amount must be greater than zero'},
            status=400,
        )

    description = data.get('description')
    if description is None:
        description = ''

    sender = data.get('sender')
    if sender is not None and sender != '':
        sender = str(sender)
    else:
        sender = None

    related_user = None
    ru_id = data.get('related_user_id')
    if ru_id is not None and ru_id != '':
        try:
            related_user = User.objects.get(pk=int(ru_id))
        except (ValueError, TypeError, User.DoesNotExist):
            return JsonResponse(
                {'status': 'error', 'message': 'related_user_id is invalid or user does not exist'},
                status=400,
            )

    if payment_type == 'contribution':
        if related_user is None:
            return JsonResponse(
                {'status': 'error', 'message': 'related_user_id is required for contribution payment'},
                status=400,
            )
        if not getattr(related_user, 'profile', None) or not related_user.profile.is_contributor:
            return JsonResponse(
                {'status': 'error', 'message': 'related_user_id must point to a contributor user'},
                status=400,
            )

    related_order = None
    ro_id = data.get('related_order_id')
    if ro_id is not None and ro_id != '':
        try:
            related_order = Order.objects.get(pk=int(ro_id))
        except (ValueError, TypeError, Order.DoesNotExist):
            return JsonResponse(
                {'status': 'error', 'message': 'related_order_id is invalid or order does not exist'},
                status=400,
            )

    payment_date = None
    raw_date = data.get('payment_date')
    if raw_date is not None and raw_date != '':
        if isinstance(raw_date, str):
            try:
                payment_date = date.fromisoformat(raw_date.strip()[:10])
            except ValueError:
                return JsonResponse(
                    {'status': 'error', 'message': 'payment_date must be ISO format YYYY-MM-DD'},
                    status=400,
                )
        else:
            return JsonResponse(
                {'status': 'error', 'message': 'payment_date must be a string YYYY-MM-DD'},
                status=400,
            )

    payment = Payment.objects.create(
        payment_type=payment_type,
        amount=amount,
        description=description,
        sender=sender,
        related_user=related_user,
        related_order=related_order,
        payment_date=payment_date,
        created_by=request.user,
    )

    return JsonResponse(
        {
            'status': 'success',
            'payment': {
                'id': payment.id,
                'amount': str(payment.amount),
                'payment_type': payment.payment_type,
                'description': payment.description,
                'sender': payment.sender,
                'related_user_id': payment.related_user_id,
                'related_order_id': payment.related_order_id,
                'payment_date': payment.payment_date.isoformat() if payment.payment_date else None,
                'created_at': payment.created_at.isoformat(),
                'created_by_id': payment.created_by_id,
            },
        },
        status=201,
    )
