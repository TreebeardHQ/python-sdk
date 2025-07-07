"""
Django instrumentation for Treebeard.

This module provides Django middleware integration to automatically clear context variables
when a request ends.
"""
import traceback

from .core import Treebeard
from .span import end_span, start_span
from .spans import SpanKind, SpanStatus, SpanStatusCode

from .internal_utils.fallback_logger import sdk_logger


class TreebeardDjangoMiddleware:
    """Django middleware for Treebeard instrumentation."""

    def __init__(self, get_response):
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain
        """
        self.get_response = get_response
        self._current_span = None


    def __call__(self, request):
        """Process the request and response.

        Args:
            request: Django HttpRequest object

        Returns:
            HttpResponse: The response from the view
        """
        try:
            # Start span immediately with path, we'll update the name after URL resolution
            self.start_initial_span(request)

            response = None

            try:
                response = self.get_response(request)
                
                # Update span name with resolved route
                trace_name = self.get_trace_name(request)
                if self._current_span:
                    self._current_span.name = trace_name
                    # Set response status code
                    if hasattr(response, 'status_code'):
                        self._current_span.set_attribute("http.status_code", response.status_code)
                        # Set span status based on HTTP status
                        if response.status_code >= 400:
                            end_span(
                                self._current_span, 
                                SpanStatus(SpanStatusCode.ERROR, f"HTTP {response.status_code}")
                            )
                        else:
                            end_span(self._current_span, SpanStatus(SpanStatusCode.OK))
                    else:
                        end_span(self._current_span, SpanStatus(SpanStatusCode.OK))
                

                return response
            except Exception as e:
                trace_name = self.get_trace_name(request)
                if self._current_span:
                    self._current_span.name = trace_name
                    # Add exception event and set error status
                    self._current_span.add_event("exception", {
                        "exception.type": type(e).__name__,
                        "exception.message": str(e)
                    })
                    end_span(self._current_span, SpanStatus(SpanStatusCode.ERROR, str(e)))
                
                raise

        except Exception:
            # If there's an error in our middleware, we still want to process the request
            if response:
                return response
            else:
                return self.get_response(request)

    def start_initial_span(self, request):
        """Start a new span immediately when request starts.

        Args:
            request: Django HttpRequest object
        """
        try:
            # Start with the raw path - we'll update this after URL resolution
            span_name = f"{request.method} {request.path}"
            
            # Check for distributed tracing headers
            span_context = None
            traceparent = request.META.get('HTTP_TRACEPARENT')
            if traceparent:
                # Parse W3C traceparent header
                parsed = Treebeard.parse_traceparent(traceparent)
                if parsed:
                    # Establish trace context from parent
                    span_context = Treebeard.establish_trace_context(
                        trace_id=parsed['trace_id'],
                        parent_span_id=parsed['parent_id']
                    )
            
            # Start span for the HTTP request
            self._current_span = start_span(
                name=span_name,
                kind=SpanKind.SERVER,
                span_context=span_context
            )
            
            # Set HTTP attributes
            self._current_span.set_attribute("http.method", request.method)
            self._current_span.set_attribute("http.url", request.build_absolute_uri())
            self._current_span.set_attribute("http.route", request.path)
            self._current_span.set_attribute("http.scheme", request.scheme)
            self._current_span.set_attribute("http.target", request.path)
            
            # Client IP
            client_ip = request.META.get('REMOTE_ADDR')
            if client_ip:
                self._current_span.set_attribute("http.client_ip", client_ip)
            
            # User agent
            user_agent = request.META.get('HTTP_USER_AGENT')
            if user_agent:
                self._current_span.set_attribute("http.user_agent", user_agent)
            
            # Headers
            if request.META.get('HTTP_REFERER'):
                self._current_span.set_attribute("http.referer", request.META.get('HTTP_REFERER'))
            if request.META.get('HTTP_X_FORWARDED_FOR'):
                self._current_span.set_attribute(
                    "http.x_forwarded_for", 
                    request.META.get('HTTP_X_FORWARDED_FOR')
                )
            if request.META.get('HTTP_X_REAL_IP'):
                self._current_span.set_attribute(
                    "http.x_real_ip", 
                    request.META.get('HTTP_X_REAL_IP')
                )
            
            # Query parameters
            if request.GET:
                for key, value in request.GET.items():
                    self._current_span.set_attribute(f"http.query.{key}", value)
            
            # Request body for POST/PUT/PATCH
            if request.method in ['POST', 'PUT', 'PATCH']:
                if request.content_type and 'json' in request.content_type:
                    try:
                        import json
                        json_data = json.loads(request.body.decode('utf-8'))
                        self._current_span.set_attribute("http.request.body.json", str(json_data))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
            

        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardDjangoMiddleware.start_initial_span: "
                f"{str(e)}: {traceback.format_exc()}"
            )

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
                elif hasattr(request.resolver_match, 'route') and request.resolver_match.route:
                    route_pattern = request.resolver_match.route
                else:
                    route_pattern = request.path
            else:
                route_pattern = request.path

            # Update the trace name with the proper pattern
            updated_name = f"{request.method} {route_pattern}"

            return updated_name

        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardDjangoMiddleware.update_trace_name: "
                f"{str(e)}: {traceback.format_exc()}"
            )

    def process_response(self, request, response, exception=None):
        """Complete the span when a request ends.

        Args:
            request: Django HttpRequest object
            response: Django HttpResponse object (may be None if exception occurred)
            exception: Exception that occurred during processing (if any)
        """
        try:
            # End the current span if it exists
            if self._current_span:
                if exception:
                    self._current_span.add_event("exception", {
                        "exception.type": type(exception).__name__,
                        "exception.message": str(exception)
                    })
                    end_span(self._current_span, SpanStatus(SpanStatusCode.ERROR, str(exception)))
                else:
                    if hasattr(response, 'status_code'):
                        self._current_span.set_attribute("http.status_code", response.status_code)
                        if response.status_code >= 400:
                            end_span(
                                self._current_span, 
                                SpanStatus(SpanStatusCode.ERROR, f"HTTP {response.status_code}")
                            )
                        else:
                            end_span(self._current_span, SpanStatus(SpanStatusCode.OK))
                    else:
                        end_span(self._current_span, SpanStatus(SpanStatusCode.OK))
            

        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardDjangoMiddleware.process_response: "
                f"{str(e)}: {traceback.format_exc()}"
            )


class TreebeardDjango:
    """Django instrumentation for Treebeard."""

    @staticmethod
    def init(**kwargs):
        """Initialize Treebeard with Django-specific defaults.

        This method should be called in your Django settings or AppConfig.
        It accepts the same parameters as Treebeard.init().

        Args:
            **kwargs: Configuration options passed to Treebeard.init()
        """
        from treebeardhq.core import Treebeard

        # Get Django settings if available
        try:
            from django.conf import settings

            # Merge Django settings with kwargs
            django_config = {}

            # Map Django settings to Treebeard config
            if hasattr(settings, 'TREEBEARD_API_KEY'):
                django_config['api_key'] = settings.TREEBEARD_API_KEY
            if hasattr(settings, 'TREEBEARD_PROJECT_NAME'):
                django_config['project_name'] = settings.TREEBEARD_PROJECT_NAME
            if hasattr(settings, 'TREEBEARD_ENDPOINT'):
                django_config['endpoint'] = settings.TREEBEARD_ENDPOINT
            if hasattr(settings, 'TREEBEARD_LOG_TO_STDOUT'):
                django_config['log_to_stdout'] = settings.TREEBEARD_LOG_TO_STDOUT
            if hasattr(settings, 'TREEBEARD_CAPTURE_STDOUT'):
                django_config['capture_stdout'] = settings.TREEBEARD_CAPTURE_STDOUT
            if hasattr(settings, 'TREEBEARD_BATCH_SIZE'):
                django_config['batch_size'] = settings.TREEBEARD_BATCH_SIZE
            if hasattr(settings, 'TREEBEARD_BATCH_AGE'):
                django_config['batch_age'] = settings.TREEBEARD_BATCH_AGE

            # Kwargs override Django settings
            config = {**django_config, **kwargs}

        except ImportError:
            # Django not available, just use kwargs
            config = kwargs

        # Initialize Treebeard
        Treebeard.init(**config)
        sdk_logger.info("Treebeard initialized for Django")

    @staticmethod
    def instrument():
        """Instrument Django application by adding middleware to settings.

        Note: This method provides guidance for manual setup since Django middleware
        needs to be configured in settings.py. The actual middleware class is
        TreebeardDjangoMiddleware.
        """
        sdk_logger.info("""
To instrument your Django application with Treebeard:

1. Add 'treebeardhq.treebeard_django.TreebeardDjangoMiddleware' to your MIDDLEWARE 
   setting in settings.py:

MIDDLEWARE = [
    # ... other middleware
    'treebeardhq.treebeard_django.TreebeardDjangoMiddleware',
    # ... other middleware
]

2. Configure Treebeard in your settings.py or apps.py:

# In settings.py
TREEBEARD_API_KEY = "your-api-key-here"
TREEBEARD_PROJECT_NAME = "your-project-name"

# Or in apps.py
from treebeardhq.treebeard_django import TreebeardDjango

class YourAppConfig(AppConfig):
    def ready(self):
        TreebeardDjango.init(
            api_key="your-api-key-here",
            project_name="your-project-name"
        )

3. The middleware will automatically start traces for each request and clear context on completion.
        """)
