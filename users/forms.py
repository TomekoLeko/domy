from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django import forms

class RegisterForm(UserCreationForm):
  email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class':'form-control'}))
  password1 = forms.CharField()
  password1.widget.attrs.update({'class': 'form-control'})
  password2 = forms.CharField()
  password2.widget.attrs.update({'class': 'form-control'})

  class Meta:
    model = User
    fields = ['username', 'email']
    widgets = {
      'username':forms.TextInput(attrs={'class':'form-control'}),
    }

class LoginForm(AuthenticationForm):
  username = forms.CharField(widget=forms.TextInput(attrs={'class':'form-control', 'placeholder:':'Username'}))
  password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))

