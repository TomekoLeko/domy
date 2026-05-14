from django.urls import path

from . import views


urlpatterns = [
    path('api/shipments/', views.api_list_unassigned_shipments, name='api_list_unassigned_shipments'),
    path('api/shipments/create/', views.api_create_shipment, name='api_create_shipment'),
]
