from django.apps import AppConfig


class DentalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dental'
    verbose_name = 'Dental Management System'

    def ready(self):
        import dental.signals  # noqa: F401
