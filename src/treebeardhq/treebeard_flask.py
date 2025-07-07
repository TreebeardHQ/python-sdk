"""
Flask instrumentation for Treebeard.

This module provides Flask integration to automatically clear context variables
when a request ends.
"""
import importlib
import traceback

from treebeardhq.log import Log
from treebeardhq.span import end_span, start_span
from treebeardhq.spans import SpanKind, SpanStatus, SpanStatusCode

from .internal_utils.fallback_logger import sdk_logger


class TreebeardFlask:
    """Flask instrumentation for Treebeard."""

    @staticmethod
    def _get_request():
        try:
            return importlib.import_module("flask").request
        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardFlask._get_request : {str(e)}: {traceback.format_exc()}")
            return None

    @staticmethod
    def instrument(app) -> None:
        """Instrument a Flask application to clear context variables on request teardown.

        Args:
            app: The Flask application to instrument
        """

        if not app:
            sdk_logger.error("TreebeardFlask: No app provided")
            return

        if getattr(app, "_treebeard_instrumented", False):
            return

        try:
            sdk_logger.info(
                "TreebeardFlask: Instrumenting Flask application")

            @app.before_request
            def start_trace():
                """Start a new span when a request starts."""
                try:
                    request = TreebeardFlask._get_request()
                    
                    # Get the route pattern (e.g., '/user/<id>' instead of '/user/123')
                    if request.url_rule:
                        route_pattern = request.url_rule.rule
                    else:
                        route_pattern = f"[unmatched] {request.path}"
                    # Create a name in the format "METHOD /path/pattern"
                    span_name = f"{request.method} {route_pattern}"
                    
                    # Check for distributed tracing headers
                    parent_context = None
                    trace_id = (
                        request.headers.get('X-Trace-Id') or 
                        request.headers.get('traceparent')
                    )
                    if trace_id:
                        # Extract trace context from traceparent header (W3C format)
                        # Format: version-trace_id-parent_id-flags
                        if '-' in trace_id:
                            parts = trace_id.split('-')
                            if len(parts) >= 3:
                                parent_context = parts[1] + parts[2]  # trace_id + parent_id
                    
                    # Start span for the HTTP request
                    span = start_span(
                        name=span_name,
                        kind=SpanKind.SERVER,
                        parent_context=parent_context
                    )
                    
                    # Set HTTP attributes
                    span.set_attribute("http.method", request.method)
                    span.set_attribute("http.url", request.url)
                    span.set_attribute("http.route", route_pattern)
                    span.set_attribute("http.scheme", request.scheme)
                    span.set_attribute("http.target", request.path)
                    if request.remote_addr:
                        span.set_attribute("http.client_ip", request.remote_addr)
                    
                    # User agent information
                    if request.user_agent:
                        span.set_attribute("http.user_agent", request.user_agent.string)
                        if request.user_agent.platform:
                            span.set_attribute("user_agent.platform", request.user_agent.platform)
                        if request.user_agent.browser:
                            span.set_attribute("user_agent.browser", request.user_agent.browser)
                        if request.user_agent.version:
                            span.set_attribute("user_agent.version", request.user_agent.version)
                    
                    # Headers
                    if request.headers.get("Referer"):
                        span.set_attribute("http.referer", request.headers.get("Referer"))
                    if request.headers.get("X-Forwarded-For"):
                        span.set_attribute(
                            "http.x_forwarded_for", 
                            request.headers.get("X-Forwarded-For")
                        )
                    if request.headers.get("X-Real-IP"):
                        span.set_attribute("http.x_real_ip", request.headers.get("X-Real-IP"))
                    
                    # Query parameters
                    if request.args:
                        for key, value in request.args.to_dict(flat=True).items():
                            span.set_attribute(f"http.query.{key}", value)
                    
                    # Request body for POST/PUT/PATCH
                    if request.method in ['POST', 'PUT', 'PATCH']:
                        if request.content_type and 'json' in request.content_type:
                            json_data = request.get_json(silent=True)
                            if json_data:
                                span.set_attribute("http.request.body.json", str(json_data))
                    
                    # Also start the legacy trace for backward compatibility
                    request_data = {
                        "remote_addr": request.remote_addr,
                        "referrer": request.referrer,
                        "user_agent": request.user_agent.string if request.user_agent else None,
                        "user_agent_platform": (
                            request.user_agent.platform if request.user_agent else None
                        ),
                        "user_agent_browser": (
                            request.user_agent.browser if request.user_agent else None
                        ),
                        "user_agent_version": (
                            request.user_agent.version if request.user_agent else None
                        ),
                        "user_agent_language": (
                            request.user_agent.language if request.user_agent else None
                        ),
                    }
                    
                    # headers
                    request_data["header_referer"] = request.headers.get("Referer")
                    request_data["header_x_forwarded_for"] = request.headers.get("X-Forwarded-For")
                    request_data["header_x_real_ip"] = request.headers.get("X-Real-IP")
                    
                    for key, value in request.args.to_dict(flat=True).items():
                        request_data[f"query_param_{key}"] = value
                    
                    if request.method in ['POST', 'PUT', 'PATCH']:
                        request_data["body_json"] = request.get_json(silent=True) or {}
                    
                    Log.start(name=span_name, request_data=request_data)
                    
                except Exception as e:
                    sdk_logger.error(
                        f"Error in TreebeardFlask.start_trace : {str(e)}: {traceback.format_exc()}")

            @app.teardown_request
            def clear_context(exc):
                try:
                    """Clear the logging context and end span when a request ends."""
                    from treebeardhq.context import LoggingContext
                    
                    # End the current span
                    current_span = LoggingContext.get_current_span()
                    if current_span:
                        if exc:
                            # Set error status and add exception event
                            current_span.add_event("exception", {
                                "exception.type": type(exc).__name__,
                                "exception.message": str(exc)
                            })
                            end_span(current_span, SpanStatus(SpanStatusCode.ERROR, str(exc)))
                        else:
                            # Set success status
                            end_span(current_span, SpanStatus(SpanStatusCode.OK))
                    
                    # Also complete the legacy trace
                    if exc:
                        Log.complete_error(error=exc)
                    else:
                        Log.complete_success()
                    
                    app._treebeard_instrumented = True
                except Exception as e:
                    sdk_logger.error(
                        f"Error in TreebeardFlask.clear_context: "
                        f"{str(e)}: {traceback.format_exc()}")

        except Exception as e:
            sdk_logger.error(
                f"Error in TreebeardFlask.instrument: "
                f"{str(e)}: {traceback.format_exc()}")
