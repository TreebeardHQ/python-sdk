from functools import wraps
from typing import Callable, Any, List

from .log import Log
from .context import LoggingContext


def treebeard_trace(func: Callable = None):
    """
    Decorator to clear contextvars after function completes.
    Usage:
        @treebeard_trace
        def ...

    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:

        try:
            Log.start()
            return func(*args, **kwargs)
        except Exception as e:
            Log.error("unknown error", error=e)
            raise  # re-raises the same exception, with full traceback
        finally:
            LoggingContext.clear()

    return wrapper
