from functools import wraps
import traceback
from typing import Callable, Any, List, Optional

from .log import Log, sdk_logger
from .context import LoggingContext


def treebeard_trace(name: Optional[str] = None):
    """
    Decorator to clear contextvars after function completes.
    Usage:
        @treebeard_trace
        def ...

        or with a name:
        @treebeard_trace(name="my_trace")
        def ...

    Args:
        name: Optional name for the trace
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                Log.start(name=name, data={"args": args}, **kwargs)
                result = func(*args, **kwargs)
                Log.complete_success(result=result)
                return result
            except Exception as e:
                Log.complete_error(error=e)
                raise  # re-raises the same exception, with full traceback
            finally:
                try:
                    LoggingContext.clear()
                except Exception as e:
                    sdk_logger.error(
                        f"Error in Log.clear : {str(e)}: {traceback.format_exc()}")
        return wrapper

    return decorator
