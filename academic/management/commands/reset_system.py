from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User, UserModule
from registration.models import Student, StudentClassHistory, Equipment
from academic.models import (
    Exam, StudentMark, Result, TeacherSubject, Subject, Combination, Paper,
    TeacherSubjectRequest, MarkSubmission, Notification
)
from discipline.models import DisciplineCase, DisciplineAuditLog, SuspensionRecord
from audit.models import AuditLog

class Command(BaseCommand):
    help = 'Clears all results, students, and users except superusers to start fresh.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting complete system data reset..."))
        
        with transaction.atomic():
            # 1. Clear Academic Data
            Result.objects.all().delete()
            StudentMark.objects.all().delete()
            MarkSubmission.objects.all().delete()
            TeacherSubjectRequest.objects.all().delete()
            TeacherSubject.objects.all().delete()
            Exam.objects.all().delete()
            Notification.objects.all().delete()
            
            # 1b. Clear Academic Structure (To remove duplicate ECO vs ECO_A etc.)
            Combination.objects.all().delete()
            Paper.objects.all().delete()
            Subject.objects.all().delete()
            
            # 2. Clear Discipline Data
            SuspensionRecord.objects.all().delete()
            DisciplineAuditLog.objects.all().delete()
            DisciplineCase.objects.all().delete()
            
            # 3. Clear Student Data
            StudentClassHistory.objects.all().delete()
            Student.objects.all().delete()
            Equipment.objects.all().delete()
            
            # 4. Clear Audit Logs
            AuditLog.objects.all().delete()
            
            # 5. Clear Users (KEEP SUPERUSERS)
            UserModule.objects.all().delete()
            
            non_superusers = User.objects.filter(is_superuser=False)
            count = non_superusers.count()
            non_superusers.delete()
            
            self.stdout.write(self.style.SUCCESS(f"Success! {count} users and all school records cleared. System is now fresh."))