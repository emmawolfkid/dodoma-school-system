import re

from django import forms
from .models import Student, Equipment

# Tanzanian mobile numbers: 07XXXXXXXX / 06XXXXXXXX or +255 7XXXXXXXX / +255 6XXXXXXXX
PHONE_PATTERN = re.compile(r'^(0[67]\d{8}|\+255[67]\d{8})$')


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        # is_archived/archived_at are system-managed via Student.archive()/
        # restore() (gated on the stricter 'delete' permission) — excluding
        # them here stops a plain 'edit'-permission user from archiving a
        # student by just posting is_archived=on through this form.
        exclude = ['is_archived', 'archived_at']

        widgets = {
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'student_class': forms.Select(attrs={'class': 'form-control', 'id': 'id_student_class'}),
            'section': forms.Select(attrs={'class': 'form-control', 'id': 'id_section'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_of_admission': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'equipments': forms.CheckboxSelectMultiple(attrs={'class': 'equipment-checkbox'}),
            'health_status': forms.Select(attrs={'class': 'form-control'}),
            'school_status': forms.Select(attrs={'class': 'form-control'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024-001'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'district': forms.TextInput(attrs={'class': 'form-control'}),
            'division': forms.TextInput(attrs={'class': 'form-control'}),
            'ward': forms.TextInput(attrs={'class': 'form-control'}),
            'village': forms.TextInput(attrs={'class': 'form-control'}),
            'tribe': forms.TextInput(attrs={'class': 'form-control'}),
            'last_school_attended': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07XXXXXXXX'}),
            'parent_phone2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07XXXXXXXX (optional)'}),
            'nearby_person_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '07XXXXXXXX'}),
        }
    
    def _clean_phone(self, field_name):
        value = self.cleaned_data.get(field_name, '').strip()
        if value and not PHONE_PATTERN.match(value):
            raise forms.ValidationError("Enter a valid phone number, e.g. 07XXXXXXXX or +2557XXXXXXXX.")
        return value

    def clean_parent_phone(self):
        return self._clean_phone('parent_phone')

    def clean_parent_phone2(self):
        return self._clean_phone('parent_phone2')

    def clean_nearby_person_phone(self):
        return self._clean_phone('nearby_person_phone')

    def clean(self):
        cleaned_data = super().clean()
        student_class = cleaned_data.get('student_class')
        section = cleaned_data.get('section')

        if student_class in ['Form 1', 'Form 2', 'Form 3', 'Form 4']:
            if section not in Student.SECTION_ORDINARY:
                raise forms.ValidationError("O-Level (Forms 1-4) must use sections A–F")

        if student_class in ['Form 5', 'Form 6']:
            if section not in Student.SECTION_ADVANCED:
                raise forms.ValidationError("A-Level (Forms 5-6) must use combinations PCB, PCM, PMC, CBG, EGM, HGK, HGL")

        return cleaned_data