from django.urls import path
from . import views
from . import carts_views

urlpatterns = [
    path ('', views.home, name='home'),
    path('products/', views.products, name='products'),
    path('add/', views.add_product, name='add_product'),
    path('edit/<int:product_id>/', views.edit_product, name='edit_product'),
    path('prices/', views.prices, name='prices'),
    path('prices/add/', views.add_price_list, name='add_price_list'),
    path('prices/save/', views.save_price, name='save_price'),
    path('change-buyer/', views.change_buyer, name='change_buyer'),
    path('cart/add/', carts_views.add_to_cart, name='add_to_cart'),
    path('cart/update/', carts_views.update_cart, name='update_cart'),
    path('cart/order/', carts_views.create_order, name='create_order'),
    path('orders/', views.orders, name='orders'),
    path('orders/update-status/', views.update_order_status, name='update_order_status'),
    path('orders/delete/<int:order_id>/', views.delete_order, name='delete_order'),
    path('orders/assign-buyer/', views.assign_buyer_to_order_item, name='assign_buyer_to_order_item'),
    path('products/delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('products/add-category/', views.add_category, name='add_category'),
    path('cart/toggle/', carts_views.toggle_cart, name='toggle_cart'),
]
