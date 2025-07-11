"""
Span API for OpenTelemetry-compliant distributed tracing.
"""
import traceback
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from .context import LoggingContext
from .spans import Span, SpanContext, SpanKind, SpanStatus, SpanStatusCode, generate_span_id, generate_trace_id
from .code_snippets import CodeSnippetExtractor


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
        _submit_span_to_core(target_span)

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
    escaped: bool = False,
    capture_code_snippets: bool = True,
    context_lines: int = 5
) -> None:
    """Record an exception as an event on a span with type, message and stack trace.

    Args:
        exception: The exception to record
        span: The span to record the exception on. If None, uses current active span.
        escaped: Whether the exception escaped the span
        capture_code_snippets: Whether to capture code snippets from traceback frames
        context_lines: Number of context lines to capture around error line
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

    # Get configuration from Treebeard singleton for code snippet capture
    from .core import Treebeard
    treebeard_instance = Treebeard()

    # Use provided params or fall back to global config
    capture_enabled = (
        capture_code_snippets if capture_code_snippets is not None
        else treebeard_instance.code_snippet_enabled
    )
    context_lines_count = (
        context_lines if context_lines is not None
        else treebeard_instance.code_snippet_context_lines
    )

    # Capture code snippets if enabled
    if capture_enabled:
        extractor = CodeSnippetExtractor(
            context_lines=context_lines_count,
            max_frames=treebeard_instance.code_snippet_max_frames,
            capture_locals=False,
            exclude_patterns=treebeard_instance.code_snippet_exclude_patterns
        )
        frame_infos = extractor.extract_from_exception(exception)
    else:
        frame_infos = []

    # Add frame information to attributes if we have any
    if frame_infos:
        for i, frame_info in enumerate(frame_infos):
            frame_prefix = f"exception.frames.{i}"
            attributes[f"{frame_prefix}.filename"] = frame_info['filename']
            attributes[f"{frame_prefix}.lineno"] = str(frame_info['lineno'])
            attributes[f"{frame_prefix}.function"] = frame_info['function']

            # Add code snippet if available
            if frame_info['code_snippet']:
                from .code_snippets import format_code_snippet
                formatted_snippet = format_code_snippet(
                    frame_info,
                    show_line_numbers=True,
                    highlight_error=True
                )
                attributes[f"{frame_prefix}.code_snippet"] = formatted_snippet

                # Add individual context lines
                for j, (line, line_num) in enumerate(
                    zip(frame_info['code_snippet'],
                        frame_info['context_line_numbers'])
                ):
                    attributes[f"{frame_prefix}.context.{line_num}"] = line

                # Mark the error line
                if frame_info['error_line_index'] >= 0:
                    error_line_num = frame_info['context_line_numbers'][frame_info['error_line_index']]
                    attributes[f"{frame_prefix}.error_lineno"] = str(
                        error_line_num)

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
