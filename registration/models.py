from django.db import models
from django.utils import timezone


class Equipment(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Student(models.Model):

    # ================= CHOICES =================

    FORM_CHOICES = [
        ('Form 1', 'Form 1'),
        ('Form 2', 'Form 2'),
        ('Form 3', 'Form 3'),
        ('Form 4', 'Form 4'),
        ('Form 5', 'Form 5'),
        ('Form 6', 'Form 6'),
    ]

    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]

    SECTION_CHOICES = [
        ('A', 'A'), ('B', 'B'), ('C', 'C'),
        ('D', 'D'), ('E', 'E'), ('F', 'F'),
        ('PCB', 'PCB'), ('PCM', 'PCM'), ('PMC', 'PMC'),
        ('CBG', 'CBG'), ('EGM', 'EGM'), ('HGK', 'HGK'), ('HGL', 'HGL'),
    ]

    SECTION_ORDINARY = ['A', 'B', 'C', 'D', 'E', 'F']
    SECTION_ADVANCED = ['PCB', 'PCM', 'PMC', 'CBG', 'EGM', 'HGK', 'HGL']

    # ================= BASIC INFO =================

    registration_number = models.CharField(max_length=100, unique=True)

    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()

    # ================= ACADEMIC =================

    student_class = models.CharField(max_length=20, choices=FORM_CHOICES)
    section = models.CharField(max_length=10, choices=SECTION_CHOICES)
    date_of_admission = models.DateField()

    # ================= LOCATION =================

    region = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    division = models.CharField(max_length=100, blank=True)
    ward = models.CharField(max_length=100)
    village = models.CharField(max_length=100)

    # ================= EXTRA =================

    tribe = models.CharField(max_length=100, blank=True)
    last_school_attended = models.CharField(max_length=255, blank=True)

    # ================= PARENT =================

    parent_name = models.CharField(max_length=255)
    parent_phone = models.CharField(max_length=20)
    parent_phone2 = models.CharField(max_length=20, blank=True)
    nearby_person_phone = models.CharField(max_length=20, blank=True)

    # ================= STATUS =================

    HEALTH_CHOICES = [
        ('Fit', 'Fit'),
        ('Sick', 'Sick'),
        ('Special Needs', 'Special Needs'),
    ]

    SCHOOL_STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Suspended', 'Suspended'),
        ('Graduated', 'Graduated'),
    ]

    health_status = models.CharField(max_length=50, choices=HEALTH_CHOICES)

    school_status = models.CharField(
        max_length=50,
        choices=SCHOOL_STATUS_CHOICES,
        default='Active'
    )

    # ================= EQUIPMENT =================

    equipments = models.ManyToManyField(Equipment, blank=True)

    # ================= MEDIA =================

    profile_photo = models.ImageField(upload_to='students/', blank=True, null=True)

    # ================= SYSTEM =================

    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    # ================= STRING =================

    def __str__(self):
        return f"{self.registration_number} - {self.first_name}"

    # ================= HELPER METHODS =================

    def archive(self):
        self.is_archived = True
        self.archived_at = timezone.now()
        self.save()

    def restore(self):
        self.is_archived = False
        self.archived_at = None
        self.save()

    # 🔥 DISCIPLINE SCORE

    def get_discipline_score(self):
        score = 0

        for case in self.discipline_cases.filter(is_archived=False):
            if case.case_type == 'minor':
                score += 1
            elif case.case_type == 'major':
                score += 3

        return score

    # 🔥 AUTO STATUS UPDATE

    def update_school_status(self):
        score = self.get_discipline_score()

        if score >= 20:
            self.school_status = 'Suspended'
        elif score >= 10:
            self.school_status = 'Suspended'
        elif score >= 5:
            self.school_status = 'Active'

        self.save()

    # ================= VALIDATION =================

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.student_class in ['Form 1', 'Form 2', 'Form 3', 'Form 4']:
            if self.section not in self.SECTION_ORDINARY:
                raise ValidationError("O-Level must use sections A–F")

        if self.student_class in ['Form 5', 'Form 6']:
            if self.section not in self.SECTION_ADVANCED:
                raise ValidationError("A-Level must use combinations")