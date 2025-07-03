from django.apps import AppConfig


class ExampleAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "example_app"
    
    def ready(self):
        """Initialize Treebeard when Django starts up."""
        from treebeardhq.treebeard_django import TreebeardDjango
        
        # Initialize Treebeard with configuration
        TreebeardDjango.init(
            project_name="django-example",
            log_to_stdout=True,  # Enable stdout logging for demo
        )
