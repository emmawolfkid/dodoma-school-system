from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Module, StaffProfile


class SignupForm(UserCreationForm):
    modules = forms.ModelMultipleChoiceField(
        queryset=Module.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class StaffProfileForm(forms.ModelForm):
    class Meta:
        model = StaffProfile
        exclude = ['user', 'created_at', 'updated_at']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_employed': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'employment_type': forms.Select(attrs={'class': 'form-control'}),
            'employment_status': forms.Select(attrs={'class': 'form-control'}),
        }
        for _field in [
            'employee_id', 'national_id', 'phone_number', 'job_title', 'qualification',
            'region', 'district', 'address', 'emergency_contact_name', 'emergency_contact_phone',
        ]:
            widgets[_field] = forms.TextInput(attrs={'class': 'form-control'})