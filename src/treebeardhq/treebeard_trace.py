import traceback
from functools import wraps
from typing import Any, Callable, Optional

from .span import end_span, start_span
from .spans import SpanKind, SpanStatus, SpanStatusCode
from .internal_utils.fallback_logger import sdk_logger


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
            # Use span name from decorator or function name
            span_name = name or func.__name__
            
            try:
                # Start span for function execution
                span = start_span(
                    name=span_name,
                    kind=SpanKind.INTERNAL
                )
                
                # Set function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                # Set argument attributes (be careful with sensitive data)
                if args:
                    span.set_attribute("function.args_count", len(args))
                if kwargs:
                    span.set_attribute("function.kwargs_count", len(kwargs))
                    # Only log non-sensitive kwargs
                    safe_kwargs = {
                        k: v for k, v in kwargs.items() 
                        if not any(
                            sensitive in k.lower() 
                            for sensitive in ['password', 'token', 'key', 'secret']
                        )
                    }
                    if safe_kwargs:
                        span.set_attribute("function.kwargs", str(safe_kwargs))
                
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Set result attributes
                if result is not None:
                    span.set_attribute("function.result_type", type(result).__name__)
                    # Only log simple result types
                    if isinstance(result, (str, int, float, bool)):
                        span.set_attribute("function.result", str(result))
                
                # Complete span with success
                end_span(span, SpanStatus(SpanStatusCode.OK))
                
                return result
                
            except Exception as e:
                # End span with error status
                if 'span' in locals():
                    span.add_event("exception", {
                        "exception.type": type(e).__name__,
                        "exception.message": str(e)
                    })
                    end_span(span, SpanStatus(SpanStatusCode.ERROR, str(e)))
                
                raise  # re-raises the same exception, with full traceback
                
        return wrapper

    return decorator
