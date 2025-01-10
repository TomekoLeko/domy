from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('finance/', views.finance_main, name='main'),
    path('finance/payment/<int:payment_id>/delete/', views.delete_payment, name='delete_payment'),
]
