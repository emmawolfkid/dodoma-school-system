from django.apps import AppConfig


class AcademicConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'academic'

    def ready(self):
        import academic.signals
        from .models import AcademicYear
        AcademicYear.get_current_year()