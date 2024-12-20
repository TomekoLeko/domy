from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from .forms import RegisterForm, LoginForm
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from products.models import PriceList
from domy.decorators import require_authenticated_staff_or_superuser
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

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
        
        profile.name = data.get('name', profile.name)
        profile.address = data.get('address', profile.address)
        profile.city = data.get('city', profile.city)
        profile.postal = data.get('postal', profile.postal)
        profile.phone = data.get('phone', profile.phone)
        
        if price_list_id := data.get('price_list'):
            profile.price_list_id = price_list_id
            
        profile.save()
        
        return JsonResponse({'status': 'success'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
