"""
Django instrumentation for Treebeard.

This module provides Django middleware integration to automatically clear context variables
when a request ends.
"""
import importlib
import traceback

from treebeardhq.context import LoggingContext
from treebeardhq.log import Log

from .internal_utils.fallback_logger import sdk_logger


class TreebeardDjangoMiddleware:
    """Django middleware for Treebeard instrumentation."""

    def __init__(self, get_response):
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain
        """
        self.get_response = get_response

    @staticmethod
    def _get_django_request_data(request):
        """Extract relevant data from Django request object.

        Args:
            request: Django HttpRequest object

        Returns:
            dict: Dictionary containing request data
        """
        try:
            request_data = {
                "remote_addr": request.META.get('REMOTE_ADDR'),
                "referrer": request.META.get('HTTP_REFERER'),
                "user_agent": request.META.get('HTTP_USER_AGENT'),
                "content_type": request.content_type,
                "content_length": request.META.get('CONTENT_LENGTH'),
            }

            # Headers
            request_data["header_referer"] = request.META.get('HTTP_REFERER')
            request_data["header_x_forwarded_for"] = request.META.get(
                'HTTP_X_FORWARDED_FOR')
            request_data["header_x_real_ip"] = request.META.get(
                'HTTP_X_REAL_IP')

            # Query parameters
            for key, value in request.GET.items():
                request_data[f"query_param_{key}"] = value

            # POST/PUT/PATCH body data
            if request.method in ['POST', 'PUT', 'PATCH']:
                if request.content_type == 'application/json':
                    try:
                        import json
                        request_data["body_json"] = json.loads(
                            request.body.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_data["body_json"] = {}
                elif request.content_type == 'application/x-www-form-urlencoded':
                    request_data["body_form"] = dict(request.POST.items())

            return request_data

        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardDjangoMiddleware._get_django_request_data: {str(e)}: {traceback.format_exc()}")
            return {}

    def __call__(self, request):
        """Process the request and response.

        Args:
            request: Django HttpRequest object

        Returns:
            HttpResponse: The response from the view
        """
        try:
            # Start trace immediately with path, we'll update the name after URL resolution
            self.start_initial_trace(request)

            response = None
            exception = None

            try:
                response = self.get_response(request)

                return response
            except Exception as e:

                raise
            finally:
                # Complete trace at the end of request processing
                trace_name = self.get_trace_name(request)

                LoggingContext.update_trace_name(trace_name)
                self.process_response(request, response, exception)

        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardDjangoMiddleware.__call__: {str(e)}: {traceback.format_exc()}")
            # If there's an error in our middleware, we still want to process the request
            return self.get_response(request)

    def start_initial_trace(self, request):
        """Start a new trace immediately when request starts.

        Args:
            request: Django HttpRequest object
        """
        try:
            # Start with the raw path - we'll update this after URL resolution
            trace_name = f"{request.method} {request.path}"
            request_data = self._get_django_request_data(request)
            Log.start(name=trace_name, request_data=request_data)

        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardDjangoMiddleware.start_initial_trace: {str(e)}: {traceback.format_exc()}")

    def get_trace_name(self, request):
        """Update the trace name with the resolved URL pattern.

        Args:
            request: Django HttpRequest object
        """
        try:
            # Now we can get the URL pattern after resolution
            if hasattr(request, 'resolver_match') and request.resolver_match:
                if request.resolver_match.url_name:
                    route_pattern = request.resolver_match.url_name
                    print(f"route_pattern 1: {route_pattern}")
                elif hasattr(request.resolver_match, 'route') and request.resolver_match.route:
                    route_pattern = request.resolver_match.route
                    print(f"route_pattern 2: {route_pattern}")
                else:
                    route_pattern = request.path
                    print(f"route_pattern 3: {route_pattern}")
            else:
                route_pattern = request.path
                print(f"route_pattern 4: {route_pattern}")

            # Update the trace name with the proper pattern
            updated_name = f"{request.method} {route_pattern}"

            return updated_name

        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardDjangoMiddleware.update_trace_name: {str(e)}: {traceback.format_exc()}")

    def process_response(self, request, response, exception=None):
        """Complete the trace when a request ends.

        Args:
            request: Django HttpRequest object
            response: Django HttpResponse object (may be None if exception occurred)
            exception: Exception that occurred during processing (if any)
        """
        try:
            if exception:
                Log.complete_error(error=exception)
            else:
                Log.complete_success()

        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardDjangoMiddleware.process_response: {str(e)}: {traceback.format_exc()}")


class TreebeardDjango:
    """Django instrumentation for Treebeard."""

    @staticmethod
    def instrument():
        """Instrument Django application by adding middleware to settings.

        Note: This method provides guidance for manual setup since Django middleware
        needs to be configured in settings.py. The actual middleware class is
        TreebeardDjangoMiddleware.
        """
        sdk_logger.info("""
To instrument your Django application with Treebeard:

1. Add 'treebeardhq.treebeard_django.TreebeardDjangoMiddleware' to your MIDDLEWARE setting in settings.py:

MIDDLEWARE = [
    # ... other middleware
    'treebeardhq.treebeard_django.TreebeardDjangoMiddleware',
    # ... other middleware
]

2. The middleware will automatically start traces for each request and clear context on completion.
        """)
