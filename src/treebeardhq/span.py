"""
Span API for OpenTelemetry-compliant distributed tracing.
"""
import traceback
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from .context import LoggingContext
from .spans import Span, SpanContext, SpanKind, SpanStatus, SpanStatusCode, generate_span_id, generate_trace_id


def start_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    span_context: Optional[SpanContext] = None
) -> Span:
    """Start a new span.

    Args:
        name: The name of the span
        kind: The kind of span (INTERNAL, SERVER, CLIENT, etc.)
        attributes: Optional attributes to set on the span
        span_context: Optional span context for distributed tracing

    Returns:
        The newly created span
    """
    # Get parent span context
    current_span = LoggingContext.get_current_span()

    if span_context:
        # Use explicit span context from distributed tracing
        parent_span_id = span_context.span_id
        trace_id = span_context.trace_id
    elif current_span:
        # Use current span as parent
        parent_span_id = current_span.span_id
        trace_id = current_span.trace_id
    else:
        # Root span
        parent_span_id = None
        trace_id = generate_trace_id()

    # Create new span
    span = Span(
        trace_id=trace_id,
        span_id=generate_span_id(),
        name=name,
        kind=kind,
        parent_span_id=parent_span_id,
        attributes=attributes or {}
    )

    # Push span to context
    LoggingContext.push_span(span)

    # Submit span to core for batching (will be added when we update core)
    _submit_span_to_core(span)

    return span


def end_span(span: Optional[Span] = None, status: Optional[SpanStatus] = None) -> None:
    """End a span.

    Args:
        span: The span to end. If None, ends the current active span.
        status: Optional status to set on the span
    """
    target_span = span or LoggingContext.get_current_span()

    if target_span and not target_span.is_ended():
        target_span.end(status)

        # If this is the current span, pop it from context
        current_span = LoggingContext.get_current_span()
        if current_span and current_span.span_id == target_span.span_id:
            LoggingContext.pop_span()


def get_current_span() -> Optional[Span]:
    """Get the currently active span.

    Returns:
        The current active span, or None if no span is active
    """
    return LoggingContext.get_current_span()


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID.

    Returns:
        The current trace ID, or None if no span is active
    """
    return LoggingContext.get_trace_id()


def set_span_attribute(key: str, value: Any, span: Optional[Span] = None) -> None:
    """Set an attribute on a span.

    Args:
        key: The attribute key
        value: The attribute value
        span: The span to set the attribute on. If None, uses current active span.
    """
    target_span = span or LoggingContext.get_current_span()
    if target_span:
        target_span.set_attribute(key, value)


def add_span_event(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    span: Optional[Span] = None
) -> None:
    """Add an event to a span.

    Args:
        name: The event name
        attributes: Optional event attributes
        span: The span to add the event to. If None, uses current active span.
    """
    target_span = span or LoggingContext.get_current_span()
    if target_span:
        target_span.add_event(name, attributes)


def record_exception_on_span(
    exception: Exception,
    span: Optional[Span] = None,
    escaped: bool = False
) -> None:
    """Record an exception as an event on a span with type, message and stack trace.

    Args:
        exception: The exception to record
        span: The span to record the exception on. If None, uses current active span.
        escaped: Whether the exception escaped the span
    """
    target_span = span or LoggingContext.get_current_span()
    if not target_span:
        return

    # Get exception information
    exception_type = type(exception).__name__
    exception_message = str(exception)
    exception_stacktrace = ''.join(traceback.format_exception(
        type(exception), exception, exception.__traceback__
    ))

    # Create exception event attributes
    attributes = {
        "exception.type": exception_type,
        "exception.message": exception_message,
        "exception.stacktrace": exception_stacktrace
    }

    if escaped:
        attributes["exception.escaped"] = "true"

    # Add exception event to span
    target_span.add_event("exception", attributes)

    # Set span status to ERROR if not already set
    if target_span.status.code == SpanStatusCode.UNSET:
        target_span.status = SpanStatus(
            SpanStatusCode.ERROR, exception_message)


@contextmanager
def span_context(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True
) -> Generator[Span, None, None]:
    """Context manager for creating and managing a span.

    Args:
        name: The name of the span
        kind: The kind of span
        attributes: Optional attributes to set on the span
        record_exception: Whether to record exceptions as span events

    Yields:
        The created span

    Example:
        with span_context("my_operation") as span:
            span.set_attribute("key", "value")
            # do work
    """
    span = start_span(name, kind, attributes)
    try:
        yield span
    except Exception as e:
        if record_exception:
            record_exception_on_span(e, span, escaped=True)
        else:
            span.status = SpanStatus(SpanStatusCode.ERROR, str(e))
        raise
    finally:
        end_span(span)


def _submit_span_to_core(span: Span) -> None:
    """Submit a span to the core for batching."""
    try:
        from .core import Treebeard
        instance = Treebeard()
        instance.add_span(span)
    except (ImportError, AttributeError):
        # Core not available, skip for now
        pass
