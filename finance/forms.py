from django import forms
from .models import Payment
from django.contrib.auth import get_user_model
from products.models import Order

User = get_user_model()

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_type', 'related_user', 'related_order', 'amount', 'payment_date', 'description']
        widgets = {
            'payment_type': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'handlePaymentTypeChange(this.value)'
            }),
            'related_user': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'handleUserChange(this.value)'
            }),
            'related_order': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': 'required'
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['related_user'].queryset = User.objects.filter(is_active=True).select_related('profile')
        self.fields['related_order'].queryset = Order.objects.all().order_by('-created_at')

        self.fields['related_user'].required = False
        self.fields['related_order'].required = False
        self.fields['description'].required = False
        self.fields['payment_date'].required = True

        # Override the label_from_instance method to show name or username
        self.fields['related_user'].label_from_instance = lambda user: (
            user.profile.name if hasattr(user, 'profile') and user.profile.name else user.username
        )
