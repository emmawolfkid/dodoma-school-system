from django import forms
from .models import DisciplineCase, SuspensionRecord


# =========================================
# 🔷 DISCIPLINE CASE FORM (FIXED)
# =========================================
class DisciplineCaseForm(forms.ModelForm):

    ACTION_CHOICES = [
        ('warning', 'Warning'),
        ('punishment', 'Punishment'),
        ('suspension', 'Suspension'),
    ]

    action_taken = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = DisciplineCase
        fields = [
            'title',
            'case_type',
            'description',
            'status',
            'severity_points',
            'date_of_incident',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'case_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'severity_points': forms.NumberInput(attrs={'class': 'form-control'}),
            'date_of_incident': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        action_taken = cleaned_data.get('action_taken')

        if not action_taken:
            self.add_error('action_taken', 'Please select an action.')

        return cleaned_data


# =========================================
# 🔷 SUSPENSION FORM (OPTIONAL - ONLY VALIDATED WHEN NEEDED)
# =========================================
class SuspensionForm(forms.ModelForm):

    class Meta:
        model = SuspensionRecord
        fields = [
            'start_date',
            'end_date',
            'actual_return_date',
            'notes'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'actual_return_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields optional initially
        for field in self.fields.values():
            field.required = False

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')

        # Only validate dates if both are provided
        if start and end and end < start:
            self.add_error('end_date', 'End date cannot be before start date.')

        return cleaned_data

    def validate_for_suspension(self):
        """Call this method when suspension is required"""
        # is_valid() runs full_clean() and populates cleaned_data — required
        # before it can be read below (calling it again after add_error() is
        # safe/idempotent and is how we get the final pass/fail result).
        self.is_valid()

        start = self.cleaned_data.get('start_date')
        end = self.cleaned_data.get('end_date')

        if not start:
            self.add_error('start_date', 'Start date is required for suspension.')
        if not end:
            self.add_error('end_date', 'End date is required for suspension.')

        return self.is_valid()