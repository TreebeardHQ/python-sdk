"""
Flask instrumentation for Treebeard.

This module provides Flask integration to automatically clear context variables
when a request ends.
"""
import importlib
import traceback

from treebeardhq.log import Log

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
                """Start a new trace when a request starts."""
                try:

                    request = TreebeardFlask._get_request()
                    # Get the route pattern (e.g., '/user/<id>' instead of '/user/123')
                    if request.url_rule:
                        route_pattern = request.url_rule.rule
                    else:
                        route_pattern = f"[unmatched] {request.path}"
                    # Create a name in the format "METHOD /path/pattern"
                    trace_name = f"{request.method} {route_pattern}"

                    request_data = {
                        "remote_addr": request.remote_addr,
                        "referrer": request.referrer,
                        "user_agent": request.user_agent.string,
                        "user_agent_platform": request.user_agent.platform,
                        "user_agent_browser": request.user_agent.browser,
                        "user_agent_version": request.user_agent.version,
                        "user_agent_language": request.user_agent.language,
                    }

                    # headers
                    request_data["header_referer"] = request.headers.get(
                        "Referer")  # often spelled like this
                    request_data["header_x_forwarded_for"] = request.headers.get(
                        "X-Forwarded-For")
                    request_data["header_x_real_ip"] = request.headers.get(
                        "X-Real-IP")

                    for key, value in request.args.to_dict(flat=True).items():
                        request_data[f"query_param_{key}"] = value

                    if request.method in ['POST', 'PUT', 'PATCH']:
                        request_data["body_json"] = request.get_json(
                            silent=True) or {}

                    Log.start(name=trace_name, request_data=request_data)
                except Exception as e:
                    sdk_logger.error(
                        f"Error in TreebeardFlask.start_trace : {str(e)}: {traceback.format_exc()}")

            @app.teardown_request
            def clear_context(exc):
                try:
                    """Clear the logging context when a request ends."""
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
