from django.urls import path
from . import views

urlpatterns = [
  path('register/', views.register, name='register'),
  path('login/', views.auth_login, name='login'),
  path('logout/', views.auth_logout, name='logout'),
]
