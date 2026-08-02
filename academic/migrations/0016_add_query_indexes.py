# Generated manually for academic query performance indexes.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('academic', '0015_alter_paper_max_marks'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['level', 'is_active'], name='acad_subj_level_active_idx'),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['name'], name='acad_subj_name_idx'),
        ),
        migrations.AddIndex(
            model_name='exam',
            index=models.Index(fields=['level', 'student_class', 'academic_year'], name='acad_exam_level_class_year_idx'),
        ),
        migrations.AddIndex(
            model_name='exam',
            index=models.Index(fields=['is_published', 'is_locked'], name='acad_exam_pub_lock_idx'),
        ),
        migrations.AddIndex(
            model_name='exam',
            index=models.Index(fields=['created_at'], name='acad_exam_created_idx'),
        ),
        migrations.AddIndex(
            model_name='paper',
            index=models.Index(fields=['subject', 'paper_number'], name='acad_paper_subject_no_idx'),
        ),
        migrations.AddIndex(
            model_name='teachersubject',
            index=models.Index(fields=['teacher', 'is_active'], name='acad_ts_teacher_active_idx'),
        ),
        migrations.AddIndex(
            model_name='teachersubject',
            index=models.Index(fields=['subject', 'student_class', 'is_active'], name='acad_ts_subject_class_idx'),
        ),
        migrations.AddIndex(
            model_name='teachersubject',
            index=models.Index(fields=['level', 'student_class', 'is_active'], name='acad_ts_level_class_idx'),
        ),
        migrations.AddIndex(
            model_name='teachersubjectrequest',
            index=models.Index(fields=['teacher', 'is_approved'], name='acad_tsr_teacher_appr_idx'),
        ),
        migrations.AddIndex(
            model_name='teachersubjectrequest',
            index=models.Index(fields=['subject', 'student_class', 'is_approved'], name='acad_tsr_subject_class_idx'),
        ),
        migrations.AddIndex(
            model_name='teachersubjectrequest',
            index=models.Index(fields=['created_at'], name='acad_tsr_created_idx'),
        ),
        migrations.AddIndex(
            model_name='studentmark',
            index=models.Index(fields=['exam', 'subject'], name='acad_mark_exam_subject_idx'),
        ),
        migrations.AddIndex(
            model_name='studentmark',
            index=models.Index(fields=['student', 'exam'], name='acad_mark_student_exam_idx'),
        ),
        migrations.AddIndex(
            model_name='studentmark',
            index=models.Index(fields=['exam', 'subject', 'paper'], name='acad_mark_exam_subj_paper_idx'),
        ),
        migrations.AddIndex(
            model_name='studentmark',
            index=models.Index(fields=['uploaded_by', 'updated_at'], name='acad_mark_uploader_time_idx'),
        ),
        migrations.AddIndex(
            model_name='result',
            index=models.Index(fields=['exam', 'position'], name='acad_result_exam_pos_idx'),
        ),
        migrations.AddIndex(
            model_name='result',
            index=models.Index(fields=['student', 'exam'], name='acad_result_student_exam_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'is_read', 'created_at'], name='acad_notif_user_read_idx'),
        ),
        migrations.AddIndex(
            model_name='marksubmission',
            index=models.Index(fields=['exam', 'student_class'], name='acad_submit_exam_class_idx'),
        ),
        migrations.AddIndex(
            model_name='marksubmission',
            index=models.Index(fields=['subject', 'student_class'], name='acad_submit_subject_class_idx'),
        ),
        migrations.AddIndex(
            model_name='marksubmission',
            index=models.Index(fields=['is_submitted', 'submitted_at'], name='acad_submit_status_time_idx'),
        ),
    ]
