from django.urls import path

from . import views


urlpatterns = [
    path('api/shipments/', views.api_list_unassigned_shipments, name='api_list_unassigned_shipments'),
    path('api/shipments/create/', views.api_create_shipment, name='api_create_shipment'),
    path('api/shipments/<int:shipment_id>/update/', views.api_update_shipment, name='api_update_shipment'),
    path('api/shipments/<int:shipment_id>/delete/', views.api_delete_shipment, name='api_delete_shipment'),
]
