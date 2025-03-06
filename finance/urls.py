from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('finance/', views.finance_main, name='main'),
    path('finance/payment/<int:payment_id>/delete/', views.delete_payment, name='delete_payment'),
    path('finance/add-multiple-transfers/', views.add_multiple_transfers, name='add_multiple_transfers'),
    path('finance/get-filtered-users/', views.get_filtered_users, name='get_filtered_users'),
    path('finance/get-filtered-orders/', views.get_filtered_orders, name='get_filtered_orders'),
    path('finance/save-multiple-payments/', views.save_multiple_payments, name='save_multiple_payments'),
    path('finance/report/', views.finance_report, name='report'),
    path('finance/delete-all-payments/', views.delete_all_payments, name='delete_all_payments'),
    path('finance/get-report-data/', views.get_report_data, name='get_report_data'),
    path('invoices/', views.invoices, name='invoices'),
]
