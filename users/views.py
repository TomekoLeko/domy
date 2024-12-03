from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from .forms import RegisterForm, LoginForm
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout

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
