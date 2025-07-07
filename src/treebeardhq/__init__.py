"""
TreebeardHQ - A Python library for forwarding logs and spans to endpoints
"""

from .context import LoggingContext
from .core import Treebeard
from .log import Log
from .span import (
    end_span, 
    get_current_span, 
    get_current_trace_id, 
    record_exception_on_span, 
    span_context, 
    start_span
)
from .spans import SpanKind, SpanStatus, SpanStatusCode
from .treebeard_flask import TreebeardFlask
from .treebeard_trace import treebeard_trace

__version__ = "0.1.0.dev1"

__all__ = [
    "Treebeard", "LoggingContext", "Log",
    "TreebeardFlask", "treebeard_trace",
    "start_span", "end_span", "span_context", "get_current_span", "get_current_trace_id",
    "record_exception_on_span", "SpanKind", "SpanStatus", "SpanStatusCode"
]
