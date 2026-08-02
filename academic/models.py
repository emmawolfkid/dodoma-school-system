from django.db import models
from django.conf import settings
from registration.models import Student
from django.utils import timezone

User = settings.AUTH_USER_MODEL


# ===============================
# ACADEMIC YEAR
# ===============================
class AcademicYear(models.Model):
    year = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.year

    @classmethod
    def get_current_year(cls):
        current_year = str(timezone.now().year)
        obj, created = cls.objects.get_or_create(
            year=current_year,
            defaults={'is_active': True}
        )
        return obj


# ===============================
# SUBJECT (FIXED)
# ===============================
class Subject(models.Model):
    LEVEL_CHOICES = (
        ('O', 'O-Level'),
        ('A', 'A-Level'),
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)

    is_core = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['level', 'is_active'], name='acad_subj_level_active_idx'),
            models.Index(fields=['name'], name='acad_subj_name_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ===============================
# COMBINATION (A-LEVEL ONLY)
# ===============================
class Combination(models.Model):
    name = models.CharField(max_length=10, unique=True)

    # 🔥 Only A-Level subjects allowed
    subjects = models.ManyToManyField(
        Subject,
        limit_choices_to={'level': 'A'}
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name.upper()

    def save(self, *args, **kwargs):
        # 🔥 normalize name (PCM, pcb → PCM)
        self.name = self.name.strip().upper()
        super().save(*args, **kwargs)

# ===============================
# EXAM
# ===============================
class Exam(models.Model):
    TERM_CHOICES = (
        ('TERM_1', 'Term 1'),
        ('TERM_2', 'Term 2'),
        ('TERM_3', 'Term 3'),
        ('MID_TERM', 'Mid Term'),
        ('MOCK', 'Mock'),
        ('PRE_NECTA', 'Pre-Necta'),
        ('FINAL', 'Final'),
    )

    LEVEL_CHOICES = (
        ('O', 'O-Level'),
        ('A', 'A-Level'),
    )

    name = models.CharField(max_length=100)
    term = models.CharField(max_length=20, choices=TERM_CHOICES, default='TERM_1')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)

    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    student_class = models.CharField(max_length=20, blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    is_published = models.BooleanField(default=False)
    show_marks = models.BooleanField(default=False)

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['level', 'student_class', 'academic_year'], name='acad_exam_level_class_year_idx'),
            models.Index(fields=['is_published', 'is_locked'], name='acad_exam_pub_lock_idx'),
            models.Index(fields=['created_at'], name='acad_exam_created_idx'),
        ]

    def __str__(self):
        return f"{self.name} - {self.student_class or self.level} ({self.academic_year.year})"


# ===============================
# PAPER (KEEP AS IS ✅)
# ===============================
class Paper(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    paper_number = models.IntegerField()
    max_marks = models.FloatField(default=100)

    class Meta:
        unique_together = ('subject', 'paper_number')
        indexes = [
            models.Index(fields=['subject', 'paper_number'], name='acad_paper_subject_no_idx'),
        ]

    def __str__(self):
        return f"{self.subject.code} - Paper {self.paper_number}"


# ===============================
# TEACHER SUBJECT ASSIGNMENT (FIXED)
# ===============================
class TeacherSubject(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    student_class = models.CharField(max_length=20)

    # 🔥 REMOVE manual level dependency risk
    level = models.CharField(
        max_length=10,
        choices=Subject.LEVEL_CHOICES,
        editable=False
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('teacher', 'subject', 'student_class')
        indexes = [
            models.Index(fields=['teacher', 'is_active'], name='acad_ts_teacher_active_idx'),
            models.Index(fields=['subject', 'student_class', 'is_active'], name='acad_ts_subject_class_idx'),
            models.Index(fields=['level', 'student_class', 'is_active'], name='acad_ts_level_class_idx'),
        ]

    def save(self, *args, **kwargs):
        # 🔥 auto-sync level from subject
        self.level = self.subject.level
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher} - {self.subject} ({self.student_class})"


# ===============================
# SUBJECT REQUEST
# ===============================
class TeacherSubjectRequest(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    student_class = models.CharField(max_length=20)

    # 🔥 auto sync like TeacherSubject
    level = models.CharField(
        max_length=10,
        choices=Subject.LEVEL_CHOICES,
        editable=False
    )

    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['teacher', 'is_approved'], name='acad_tsr_teacher_appr_idx'),
            models.Index(fields=['subject', 'student_class', 'is_approved'], name='acad_tsr_subject_class_idx'),
            models.Index(fields=['created_at'], name='acad_tsr_created_idx'),
        ]

    def save(self, *args, **kwargs):
        self.level = self.subject.level
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher} - {self.subject} ({self.student_class})"


# ===============================
# STUDENT MARKS (CRITICAL FIX)
# ===============================
class StudentMark(models.Model):
    # PROTECT: an accidental Student hard-delete must not silently wipe
    # exam marks — archive the student instead of deleting.
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, null=True, blank=True)

    marks = models.FloatField(default=0)

    # 🔥 KEEP ONLY ONE ABSENT FIELD
    is_absent = models.BooleanField(default=False)

    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    last_updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="updated_marks"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # unique_together on a nullable FK doesn't work on Postgres (NULL != NULL),
        # so paper=None rows (O-Level, single mark per subject) aren't protected by it.
        # Two conditional constraints cover both cases explicitly.
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'exam', 'subject', 'paper'],
                name='acad_mark_unique_with_paper',
                condition=models.Q(paper__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['student', 'exam', 'subject'],
                name='acad_mark_unique_without_paper',
                condition=models.Q(paper__isnull=True),
            ),
        ]
        indexes = [
            models.Index(fields=['exam', 'subject'], name='acad_mark_exam_subject_idx'),
            models.Index(fields=['student', 'exam'], name='acad_mark_student_exam_idx'),
            models.Index(fields=['exam', 'subject', 'paper'], name='acad_mark_exam_subj_paper_idx'),
            models.Index(fields=['uploaded_by', 'updated_at'], name='acad_mark_uploader_time_idx'),
        ]

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.marks}"


# ===============================
# RESULT
# ===============================
class Result(models.Model):
    # PROTECT — see StudentMark above; official results must not vanish
    # silently on a Student hard-delete.
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)

    total_points = models.IntegerField(default=0)
    division = models.CharField(max_length=20, blank=True)

    position = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position']
        indexes = [
            models.Index(fields=['exam', 'position'], name='acad_result_exam_pos_idx'),
            models.Index(fields=['student', 'exam'], name='acad_result_student_exam_idx'),
        ]

    def __str__(self):
        return f"{self.student} - {self.division}"


# ===============================
# NOTIFICATIONS
# ===============================
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    message = models.TextField()
    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at'], name='acad_notif_user_read_idx'),
        ]

    def __str__(self):
        return f"{self.user} - {self.message[:20]}"
    
class MarkSubmission(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    student_class = models.CharField(max_length=20)

    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('exam', 'subject', 'student_class')
        indexes = [
            models.Index(fields=['exam', 'student_class'], name='acad_submit_exam_class_idx'),
            models.Index(fields=['subject', 'student_class'], name='acad_submit_subject_class_idx'),
            models.Index(fields=['is_submitted', 'submitted_at'], name='acad_submit_status_time_idx'),
        ]

    def __str__(self):
        return f"{self.subject} - {self.student_class} - {self.exam}"
