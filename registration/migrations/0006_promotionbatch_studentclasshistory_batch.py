# Generated manually for reliable promotion batches.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0005_equipment_indexes_studentclasshistory'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PromotionBatch',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('academic_year', models.CharField(max_length=20)),
                ('action_type', models.CharField(choices=[('promotion', 'Promotion'), ('graduation', 'Graduation'), ('mixed', 'Mixed Promotion and Graduation')], default='promotion', max_length=20)),
                ('selected_classes', models.JSONField(blank=True, default=list)),
                ('promoted_count', models.PositiveIntegerField(default=0)),
                ('graduated_count', models.PositiveIntegerField(default=0)),
                ('skipped_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_reverted', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('reverted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reverted_promotion_batches', to=settings.AUTH_USER_MODEL)),
                ('reverted_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='studentclasshistory',
            name='batch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='history_records', to='registration.promotionbatch'),
        ),
        migrations.AddIndex(
            model_name='promotionbatch',
            index=models.Index(fields=['academic_year', 'created_at'], name='reg_promobatch_year_time_idx'),
        ),
        migrations.AddIndex(
            model_name='promotionbatch',
            index=models.Index(fields=['is_reverted', 'created_at'], name='reg_promobatch_reverted_idx'),
        ),
        migrations.AddIndex(
            model_name='studentclasshistory',
            index=models.Index(fields=['batch', 'changed_at'], name='reg_history_batch_time_idx'),
        ),
    ]
