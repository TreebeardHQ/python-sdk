from functools import wraps
from typing import Callable, Any, List, Optional

from .log import Log
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
                Log.start(name=name)
                return func(*args, **kwargs)
            except Exception as e:
                Log.error("unknown error", error=e)
                raise  # re-raises the same exception, with full traceback
            finally:
                LoggingContext.clear()

        return wrapper

    return decorator
