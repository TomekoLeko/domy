from django.urls import path
from . import views

urlpatterns = [
    path('products/', views.products, name='products'),
    path('add/', views.add_product, name='add_product'),
    path('edit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('prices/', views.prices, name='prices'),
    path('prices/add/', views.add_price_list, name='add_price_list'),
    path('prices/save/', views.save_price, name='save_price'),
]
