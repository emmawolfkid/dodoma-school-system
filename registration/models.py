from django.db import models
from django.utils import timezone
import uuid


class Equipment(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name'], name='reg_equipment_name_idx'),
        ]


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

    class Meta:
        indexes = [
            models.Index(fields=['student_class', 'school_status', 'is_archived'], name='reg_student_class_status_idx'),
            models.Index(fields=['student_class', 'section', 'school_status', 'is_archived'], name='reg_student_class_section_idx'),
            models.Index(fields=['first_name', 'last_name'], name='reg_student_name_idx'),
            models.Index(fields=['created_at'], name='reg_student_created_idx'),
        ]

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


class StudentClassHistory(models.Model):
    # PROTECT — promotion/graduation history must survive a Student
    # hard-delete rather than vanishing silently with it.
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='class_history')
    from_class = models.CharField(max_length=20)
    to_class = models.CharField(max_length=20)
    from_section = models.CharField(max_length=10, blank=True)
    to_section = models.CharField(max_length=10, blank=True)
    academic_year = models.CharField(max_length=20)
    changed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)
    batch = models.ForeignKey(
        'PromotionBatch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='history_records'
    )

    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['student', 'changed_at'], name='reg_history_student_time_idx'),
            models.Index(fields=['academic_year', 'from_class', 'to_class'], name='reg_history_year_classes_idx'),
            models.Index(fields=['batch', 'changed_at'], name='reg_history_batch_time_idx'),
        ]

    def __str__(self):
        return f"{self.student.registration_number}: {self.from_class} to {self.to_class}"


class PromotionBatch(models.Model):
    ACTION_PROMOTION = 'promotion'
    ACTION_GRADUATION = 'graduation'
    ACTION_MIXED = 'mixed'

    ACTION_CHOICES = [
        (ACTION_PROMOTION, 'Promotion'),
        (ACTION_GRADUATION, 'Graduation'),
        (ACTION_MIXED, 'Mixed Promotion and Graduation'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.CharField(max_length=20)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_PROMOTION)
    selected_classes = models.JSONField(default=list, blank=True)
    promoted_count = models.PositiveIntegerField(default=0)
    graduated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_reverted = models.BooleanField(default=False)
    reverted_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reverted_promotion_batches'
    )
    reverted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['academic_year', 'created_at'], name='reg_promobatch_year_time_idx'),
            models.Index(fields=['is_reverted', 'created_at'], name='reg_promobatch_reverted_idx'),
        ]

    @property
    def total_changed(self):
        return self.promoted_count + self.graduated_count

    def __str__(self):
        return f"{self.academic_year} promotion batch {self.id}"
