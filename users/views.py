from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from .forms import RegisterForm, LoginForm
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from products.models import PriceList
from domy.decorators import require_authenticated_staff_or_superuser
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
import json

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

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


# --- API Auth (React frontend: POST JSON login/email + password, JWT in response) ---

@api_view(["POST"])
def api_login(request):
    """
    POST /api/auth/login/ with body { "login": "user@example.com" or "username", "password": "..." }.
    Also accepts "email" instead of "login" (backward compatible). Returns JWT token and user.
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
    refresh = RefreshToken.for_user(user)
    return Response({
        "token": str(refresh.access_token),
        "refresh": str(refresh),
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
    """POST /api/auth/logout/. Optional: clear server session; for JWT, frontend removes token."""
    logout(request)
    return Response({"ok": True}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_me(request):
    """GET /api/auth/me/. Returns current user (id, username, email, is_superuser)."""
    user = request.user
    return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
        "is_superuser": user.is_superuser,
    })
