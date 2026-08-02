# Generated manually for student query performance indexes.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0003_student_archived_at'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='student',
            index=models.Index(fields=['student_class', 'school_status', 'is_archived'], name='reg_student_class_status_idx'),
        ),
        migrations.AddIndex(
            model_name='student',
            index=models.Index(fields=['student_class', 'section', 'school_status', 'is_archived'], name='reg_student_class_section_idx'),
        ),
        migrations.AddIndex(
            model_name='student',
            index=models.Index(fields=['first_name', 'last_name'], name='reg_student_name_idx'),
        ),
        migrations.AddIndex(
            model_name='student',
            index=models.Index(fields=['created_at'], name='reg_student_created_idx'),
        ),
    ]
