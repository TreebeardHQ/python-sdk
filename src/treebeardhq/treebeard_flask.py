"""
Flask instrumentation for Treebeard.

This module provides Flask integration to automatically clear context variables
when a request ends.
"""
from .context import LoggingContext
from .internal_utils.fallback_logger import fallback_logger


class TreebeardFlask:
    """Flask instrumentation for Treebeard."""

    @staticmethod
    def instrument(app) -> None:
        """Instrument a Flask application to clear context variables on request teardown.

        Args:
            app: The Flask application to instrument
        """
        fallback_logger.info("TreebeardFlask: Instrumenting Flask application")

        @app.teardown_request
        def clear_context(exc):
            """Clear the logging context when a request ends."""
            LoggingContext.clear()
