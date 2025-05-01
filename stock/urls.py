from django.urls import path
from . import views

urlpatterns = [
    path('', views.stock_main, name='stock_main'),
    path('suppliers/', views.suppliers, name='suppliers'),
    path('suppliers/add/', views.add_supplier, name='add_supplier'),
    path('suppliers/edit/<int:supplier_id>/', views.edit_supplier, name='edit_supplier'),
    path('suppliers/delete/<int:supplier_id>/', views.delete_supplier, name='delete_supplier'),
    path('supply-orders/add/', views.add_supply_order, name='add_supply_order'),
    path('supply-orders/assign-invoice/', views.assign_invoice, name='assign_invoice'),
    path('supply-orders/delete/<int:supply_order_id>/', views.delete_supply_order, name='delete_supply_order'),
    path('create-reduction/', views.create_stock_reduction, name='create_stock_reduction'),
    path('stock-levels/', views.stock_levels, name='stock_levels'),
    path('api/products/', views.api_products, name='api_products'),
    path('product-stock-levels/<int:product_id>/', views.product_stock_levels, name='product_stock_levels'),
] 
