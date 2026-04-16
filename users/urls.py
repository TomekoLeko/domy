from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.auth_login, name='login'),
    path('logout/', views.auth_logout, name='logout'),
    path('users/', views.users_list, name='users_list'),
    path('update/', views.update_user_profile, name='update_user_profile'),
    # API auth (React: POST JSON email+password, JWT in response)
    path('api/auth/login/', views.api_login, name='api_login'),
    path('api/auth/logout/', views.api_logout, name='api_logout'),
    path('api/auth/csrf/', views.api_csrf, name='api_csrf'),
    path('api/auth/me/', views.api_me, name='api_me'),
]
