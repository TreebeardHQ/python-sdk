from django.apps import AppConfig


class ExampleAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "example_app"

    def ready(self):
        """Initialize Lumberjack when Django starts up."""
        from lumberjack_sdk.lumberjack_django import LumberjackDjango

        # Initialize Lumberjack with configuration
        LumberjackDjango.init(
            project_name="django-example",
            log_to_stdout=True,  # Enable stdout logging for demo
        )
