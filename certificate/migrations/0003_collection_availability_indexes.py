# Generated manually for certificate and result-slip availability tracking.

from django.db import migrations, models


def copy_legacy_received_flag(apps, schema_editor):
    GraduateCollection = apps.get_model('certificate', 'GraduateCollection')
    GraduateCollection.objects.filter(is_received_at_school=True).update(
        certificate_received_at_school=True,
        result_slip_received_at_school=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('certificate', '0002_rename_date_collected_graduatecollection_date_issued_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='graduatecollection',
            name='certificate_received_at_school',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='graduatecollection',
            name='certificate_unavailable_reason',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='graduatecollection',
            name='result_slip_received_at_school',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='graduatecollection',
            name='result_slip_unavailable_reason',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(copy_legacy_received_flag, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='graduatecollection',
            index=models.Index(fields=['certificate_collected', 'result_slip_collected'], name='cert_collection_status_idx'),
        ),
        migrations.AddIndex(
            model_name='graduatecollection',
            index=models.Index(fields=['certificate_received_at_school', 'result_slip_received_at_school'], name='cert_received_status_idx'),
        ),
    ]
