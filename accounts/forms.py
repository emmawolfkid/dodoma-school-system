from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Module


class SignupForm(UserCreationForm):
    modules = forms.ModelMultipleChoiceField(
        queryset=Module.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']