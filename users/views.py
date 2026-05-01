from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from .forms import RegisterForm, LoginForm
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from products.models import PriceList
from .models import Profile
from domy.decorators import require_authenticated_staff_or_superuser
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
import json

from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from finance.models import MonthlyContributionUsage

def register(request):
  if request.user.is_authenticated:
    return HttpResponseRedirect(reverse('home'))
  else:
    if request.method == 'POST':
      form = RegisterForm(request.POST)
      if form.is_valid():
        form.save()
        homeurl = reverse('home')
        return HttpResponseRedirect(homeurl)
    else:
      form = RegisterForm()
    return render (request, 'users/register.html', {'form': form})

def auth_login(request):
  if request.user.is_authenticated:
    return HttpResponseRedirect(reverse('home'))
  else:
    if request.method == 'POST':
      form = LoginForm(request=request, data=request.POST)
      if form.is_valid():
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
          login(request,user)
          return HttpResponseRedirect(reverse('home'))
        print(user)
    else:
      form = LoginForm()

    return render(request, 'users/login.html', {'form': form})

def auth_logout(request):
  logout(request)
  return HttpResponseRedirect(reverse('login'))

@require_authenticated_staff_or_superuser
def users_list(request):
    users = User.objects.all().prefetch_related('profile')
    price_lists = PriceList.objects.all()
    return render(request, 'users/users.html', {
        'users': users,
        'price_lists': price_lists
    })

@require_POST
@require_authenticated_staff_or_superuser
def update_user_profile(request):
    data = json.loads(request.body)
    user_id = data.get('user_id')
    
    try:
        user = User.objects.get(id=user_id)
        profile = user.profile

        # Update User model fields
        user.first_name = data.get('first_name', '')
        user.last_name = data.get('last_name', '')
        user.email = data.get('email', '')
        user.save()

        # Update Profile model fields
        profile.name = data.get('name', '')
        profile.phone = data.get('phone', '')
        profile.address = data.get('address', '')
        profile.city = data.get('city', '')
        profile.postal = data.get('postal', '')
        profile.is_beneficiary = data.get('is_beneficiary', False)
        profile.monthly_limit = data.get('monthly_limit', '')
        discount_rate_percent = data.get('discount_rate_percent')
        profile.discount_rate_percent = discount_rate_percent if discount_rate_percent not in ("", None) else None
        if data.get('price_list'):
            profile.price_list_id = data.get('price_list')
        else:
            profile.price_list = None
        profile.save()

        return JsonResponse({
            'status': 'success',
            'message': 'Profile updated successfully'
        })
    except User.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'User not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def _api_staff_forbidden_response():
    return Response(
        {"detail": "Brak uprawnień do tej operacji"},
        status=status.HTTP_403_FORBIDDEN,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_users_list(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return _api_staff_forbidden_response()

    users = User.objects.all().prefetch_related('profile')
    price_lists = PriceList.objects.all()

    serialized_users = []
    for user in users:
        profile, _ = Profile.objects.get_or_create(user=user)
        display_name = (
            profile.name
            or f"{user.first_name} {user.last_name}".strip()
            or f"{user.username} (login)"
        )
        serialized_users.append({
            "id": user.id,
            "username": user.username,
            "display_name": display_name,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "email": user.email or "",
            "profile": {
                "name": profile.name or "",
                "phone": profile.phone or "",
                "address": profile.address or "",
                "city": profile.city or "",
                "postal": profile.postal or "",
                "is_beneficiary": bool(profile.is_beneficiary),
                "monthly_limit": profile.monthly_limit,
                "discount_rate_percent": (
                    str(profile.discount_rate_percent)
                    if profile.discount_rate_percent is not None
                    else None
                ),
                "price_list_id": profile.price_list_id,
            },
        })

    serialized_price_lists = [
        {"id": price_list.id, "name": price_list.name}
        for price_list in price_lists
    ]

    return Response({
        "users": serialized_users,
        "price_lists": serialized_price_lists,
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_update_user_profile(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return _api_staff_forbidden_response()

    data = request.data
    user_id = data.get("user_id")
    if not user_id:
        return Response(
            {"detail": "Pole user_id jest wymagane"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(id=user_id)
        profile, _ = Profile.objects.get_or_create(user=user)

        user.first_name = data.get("first_name", "")
        user.last_name = data.get("last_name", "")
        user.email = data.get("email", "")
        user.save()

        profile.name = data.get("name", "")
        profile.phone = data.get("phone", "")
        profile.address = data.get("address", "")
        profile.city = data.get("city", "")
        profile.postal = data.get("postal", "")
        profile.is_beneficiary = bool(data.get("is_beneficiary", False))
        monthly_limit = data.get("monthly_limit")
        profile.monthly_limit = monthly_limit if monthly_limit not in ("", None) else None
        discount_rate_percent = data.get("discount_rate_percent")
        profile.discount_rate_percent = (
            discount_rate_percent if discount_rate_percent not in ("", None) else None
        )

        if data.get("price_list"):
            profile.price_list_id = data.get("price_list")
        else:
            profile.price_list = None
        profile.save()

        return Response(
            {"status": "success", "message": "Profile updated successfully"},
            status=status.HTTP_200_OK,
        )
    except User.DoesNotExist:
        return Response(
            {"status": "error", "message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_user_monthly_contributions(request, user_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return _api_staff_forbidden_response()

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"detail": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    profile, _ = Profile.objects.get_or_create(user=target_user)
    usages = (
        MonthlyContributionUsage.objects
        .filter(profile=profile)
        .prefetch_related('order_items', 'order_items__product')
        .order_by('-year', '-month')
    )

    monthly_usage = []
    pinned_order_items = []
    seen_order_item_ids = set()

    for usage in usages:
        usage_order_items = list(usage.order_items.all())
        monthly_usage.append({
            "id": usage.id,
            "year": usage.year,
            "month": usage.month,
            "limit": str(usage.limit),
            "total_usage": str(usage.total_usage),
            "remaining_limit": str(usage.remaining_limit),
            "order_items_count": len(usage_order_items),
        })

        for order_item in usage_order_items:
            if order_item.id in seen_order_item_ids:
                continue
            seen_order_item_ids.add(order_item.id)
            pinned_order_items.append({
                "id": order_item.id,
                "order_id": order_item.order_id,
                "product_id": order_item.product_id,
                "product_name": order_item.product.name,
                "price": str(order_item.price),
                "buyer_id": order_item.buyer_id,
            })

    return Response(
        {
            "user_id": target_user.id,
            "monthly_usage": monthly_usage,
            "pinned_order_items": pinned_order_items,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_delete_monthly_contribution_usage(request, usage_id):
    if not (request.user.is_staff or request.user.is_superuser):
        return _api_staff_forbidden_response()

    try:
        usage = MonthlyContributionUsage.objects.prefetch_related('order_items').get(id=usage_id)
    except MonthlyContributionUsage.DoesNotExist:
        return Response(
            {"detail": "MonthlyContributionUsage not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if usage.order_items.exists():
        return Response(
            {"detail": "Nie można usunąć wpisu: obiekt ma przypięte OrderItems."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    usage.delete()
    return Response({"status": "success"}, status=status.HTTP_200_OK)


# --- API Auth (React frontend: sesja + cookie, bez JWT) ---

@api_view(["POST"])
def api_login(request):
    """
    POST /api/auth/login/ with body { "login": "user@example.com" or "username", "password": "..." }.
    Also accepts "email" instead of "login". On success sets session (cookie sessionid)
    and returns only user data. Frontend must send X-CSRFToken and credentials: 'include'.
    """
    login_value = request.data.get("login") or request.data.get("email")
    password = request.data.get("password")
    if not login_value or not password:
        return Response(
            {"detail": "Login (or email) and password required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        if "@" in login_value:
            user = User.objects.get(email=login_value)
        else:
            user = User.objects.get(username=login_value)
    except User.DoesNotExist:
        return Response(
            {"detail": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if not user.check_password(password):
        return Response(
            {"detail": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    login(request, user)
    return Response({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email or "",
            "is_superuser": user.is_superuser,
        },
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_logout(request):
    """POST /api/auth/logout/. Clears server session. Send credentials: 'include' and X-CSRFToken."""
    logout(request)
    return Response({"ok": True}, status=status.HTTP_200_OK)


@ensure_csrf_cookie
@api_view(["GET"])
def api_me(request):
    """
    GET /api/auth/me/.

    Sets CSRF cookie (csrftoken) and returns the CSRF token value in JSON so SPA running on a different origin
    can send it as `X-CSRFToken` for subsequent POST/PUT/PATCH/DELETE.

    Returns:
      - `csrfToken`: string
      - `user`: object or null
    """
    # DRF passes a `rest_framework.request.Request` into the view;
    # Django's `get_token` expects a real `django.http.HttpRequest`.
    django_request = getattr(request, "_request", request)
    csrf_token = get_token(django_request)

    if request.user.is_authenticated:
        user_obj = request.user
        user = {
            "id": user_obj.id,
            "username": user_obj.username,
            "email": user_obj.email or "",
            "is_superuser": user_obj.is_superuser,
        }
    else:
        user = None

    return Response({"csrfToken": csrf_token, "user": user})


@ensure_csrf_cookie
@api_view(["GET"])
def api_csrf(request):
    """
    GET /api/auth/csrf/.

    Backward-compatible alias for SPAs that fetch a CSRF token from this route.
    Returns the same payload as `api_me`.
    """
    # Same behavior as `api_me`, but without calling `api_me(request)` directly.
    # Otherwise we'd pass DRF's `Request` object into a DRF-decorated view,
    # which expects a Django `HttpRequest`.
    django_request = getattr(request, "_request", request)
    csrf_token = get_token(django_request)

    if request.user.is_authenticated:
        user_obj = request.user
        user = {
            "id": user_obj.id,
            "username": user_obj.username,
            "email": user_obj.email or "",
            "is_superuser": user_obj.is_superuser,
        }
    else:
        user = None

    return Response({"csrfToken": csrf_token, "user": user})
