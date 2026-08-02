# Generated manually for registration scalability and promotion history.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0004_add_student_query_indexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='equipment',
            options={'ordering': ['name']},
        ),
        migrations.AddIndex(
            model_name='equipment',
            index=models.Index(fields=['name'], name='reg_equipment_name_idx'),
        ),
        migrations.CreateModel(
            name='StudentClassHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_class', models.CharField(max_length=20)),
                ('to_class', models.CharField(max_length=20)),
                ('from_section', models.CharField(blank=True, max_length=10)),
                ('to_section', models.CharField(blank=True, max_length=10)),
                ('academic_year', models.CharField(max_length=20)),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('note', models.CharField(blank=True, max_length=255)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_history', to='registration.student')),
            ],
            options={
                'ordering': ['-changed_at'],
            },
        ),
        migrations.AddIndex(
            model_name='studentclasshistory',
            index=models.Index(fields=['student', 'changed_at'], name='reg_history_student_time_idx'),
        ),
        migrations.AddIndex(
            model_name='studentclasshistory',
            index=models.Index(fields=['academic_year', 'from_class', 'to_class'], name='reg_history_year_classes_idx'),
        ),
    ]
