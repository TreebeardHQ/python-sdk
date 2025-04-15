"""
Flask instrumentation for Treebeard.

This module provides Flask integration to automatically clear context variables
when a request ends.
"""
import importlib
from treebeardhq.log import Log
from .context import LoggingContext
from .internal_utils.fallback_logger import fallback_logger


class TreebeardFlask:
    """Flask instrumentation for Treebeard."""

    @staticmethod
    def _get_request():
        return importlib.import_module("flask").request

    @staticmethod
    def instrument(app) -> None:
        """Instrument a Flask application to clear context variables on request teardown.

        Args:
            app: The Flask application to instrument
        """

        if getattr(app, "_treebeard_instrumented", False):
            return

        fallback_logger.info("TreebeardFlask: Instrumenting Flask application")

        @app.before_request
        def start_trace():
            """Start a new trace when a request starts."""
            request = TreebeardFlask._get_request()
            # Get the route pattern (e.g., '/user/<id>' instead of '/user/123')
            if request.url_rule:
                route_pattern = request.url_rule.rule
            else:
                route_pattern = f"[unmatched] {request.path}"
            # Create a name in the format "METHOD /path/pattern"
            trace_name = f"{request.method} {route_pattern}"
            Log.start(name=trace_name)

        @app.teardown_request
        def clear_context(exc):
            """Clear the logging context when a request ends."""
            if exc:
                Log.error("Request teardown with exception", error=exc)

            LoggingContext.clear()

        app._treebeard_instrumented = True
