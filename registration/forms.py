from django import forms
from .models import Student, Equipment


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = '__all__'
        
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