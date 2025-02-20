from django import template
from finance.models import Payment

register = template.Library()

@register.filter
def payment_type_label(value):
    """Convert payment type value to its display label"""
    payment_types_dict = dict(Payment.PAYMENT_TYPES)
    return payment_types_dict.get(value, value) 
