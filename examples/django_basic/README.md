# Lumberjack Django Example

This example demonstrates how to integrate Lumberjack logging with a Django application using the LumberjackDjangoMiddleware.

## Setup

1. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set your Lumberjack API key as an environment variable:

   ```bash
   export LUMBERJACK_API_KEY="your-api-key-here"
   ```

3. Run the Django development server:
   ```bash
   python manage.py runserver
   ```

## Configuration

This example shows two ways to configure Lumberjack in Django:

### Method 1: Using AppConfig (Recommended)

In `example_app/apps.py`:

```python
from django.apps import AppConfig
from lumberjack_sdk.lumberjack_django import LumberjackDjango

class ExampleAppConfig(AppConfig):
    name = "example_app"

    def ready(self):
        LumberjackDjango.init(
            project_name="django-example",
            log_to_stdout=True,
        )
```

### Method 2: Using Django Settings

In `settings.py`:

```python
LUMBERJACK_API_KEY = "your-api-key-here"
LUMBERJACK_PROJECT_NAME = "django-example"
LUMBERJACK_LOG_TO_STDOUT = True
```

Then call `LumberjackDjango.init()` in your AppConfig's `ready()` method (it will pick up the settings automatically).

## Available Endpoints

- `GET /` - Home page with basic logging
- `GET /products/` - Products list with data logging
- `GET /slow/` - Slow operation to demonstrate performance logging
- `GET /error/` - Random error endpoint to demonstrate error logging
- `GET /user/<id>/` - User profile with parameter logging

## How It Works

The Lumberjack middleware is configured in `django_basic/settings.py`:

```python
MIDDLEWARE = [
    # ... other middleware
    "lumberjack_sdk.lumberjack_django.LumberjackDjangoMiddleware",
]
```

The middleware automatically:

- Starts a new trace for each request
- Captures request metadata (headers, query params, etc.)
- Completes the trace when the request finishes
- Handles errors and logs them appropriately

## Example Usage

```bash
# Test basic functionality
curl http://localhost:8000/

# Test with parameters
curl http://localhost:8000/user/123/

# Test error handling
curl http://localhost:8000/error/

# Test slow operations
curl http://localhost:8000/slow/
```

Each request will be automatically traced and logged to Lumberjack with context preserved throughout the request lifecycle.
