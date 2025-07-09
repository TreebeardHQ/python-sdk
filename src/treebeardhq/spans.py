"""
OpenTelemetry-compliant span data structures and utilities.
"""
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SpanKind(Enum):
    """OpenTelemetry span kinds."""
    UNSPECIFIED = 0
    INTERNAL = 1
    SERVER = 2
    CLIENT = 3
    PRODUCER = 4
    CONSUMER = 5


class SpanStatusCode(Enum):
    """OpenTelemetry span status codes."""
    UNSET = 0
    OK = 1
    ERROR = 2


@dataclass
class SpanStatus:
    """OpenTelemetry span status."""
    code: SpanStatusCode = SpanStatusCode.UNSET
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"code": self.code.value}
        if self.message:
            result["message"] = self.message
        return result


@dataclass
class SpanEvent:
    """OpenTelemetry span event."""
    name: str
    time_unix_nano: int
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "timeUnixNano": self.time_unix_nano
        }
        if self.attributes:
            result["attributes"] = [
                {"key": k, "value": {"stringValue": str(v)}}
                for k, v in self.attributes.items()
            ]
        return result


@dataclass
class SpanLink:
    """OpenTelemetry span link."""
    trace_id: str
    span_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "traceId": self.trace_id,
            "spanId": self.span_id
        }
        if self.attributes:
            result["attributes"] = [
                {"key": k, "value": {"stringValue": str(v)}}
                for k, v in self.attributes.items()
            ]
        return result


@dataclass
class Span:
    """OpenTelemetry span representation."""
    trace_id: str
    span_id: str
    name: str
    kind: SpanKind = SpanKind.INTERNAL
    start_time_unix_nano: Optional[int] = None
    end_time_unix_nano: Optional[int] = None
    parent_span_id: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    links: List[SpanLink] = field(default_factory=list)
    status: SpanStatus = field(default_factory=SpanStatus)

    def __post_init__(self):
        if self.start_time_unix_nano is None:
            self.start_time_unix_nano = time.time_ns()

    def end(self, status: Optional[SpanStatus] = None) -> None:
        """End the span with optional status."""
        self.end_time_unix_nano = time.time_ns()
        if status:
            self.status = status

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        event = SpanEvent(
            name=name,
            time_unix_nano=time.time_ns(),
            attributes=attributes or {}
        )
        self.events.append(event)

    def add_link(self, trace_id: str, span_id: str,
                 attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add a link to another span."""
        link = SpanLink(
            trace_id=trace_id,
            span_id=span_id,
            attributes=attributes or {}
        )
        self.links.append(link)

    def is_ended(self) -> bool:
        """Check if the span has been ended."""
        return self.end_time_unix_nano is not None

    def to_otel_dict(self) -> Dict[str, Any]:
        """Convert span to OpenTelemetry JSON format."""
        result = {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "name": self.name,
            "kind": self.kind.value,
            "startTimeUnixNano": self.start_time_unix_nano
        }

        if self.parent_span_id:
            result["parentSpanId"] = self.parent_span_id

        if self.end_time_unix_nano:
            result["endTimeUnixNano"] = self.end_time_unix_nano

        if self.attributes:
            result["attributes"] = [
                {"key": k, "value": _format_attribute_value(v)}
                for k, v in self.attributes.items()
            ]

        if self.events:
            result["events"] = [event.to_dict() for event in self.events]

        if self.links:
            result["links"] = [link.to_dict() for link in self.links]

        if self.status.code != SpanStatusCode.UNSET:
            result["status"] = self.status.to_dict()

        return result


def _format_attribute_value(value: Any) -> Dict[str, Any]:
    """Format attribute value according to OpenTelemetry spec."""
    if isinstance(value, str):
        return {"stringValue": value}
    elif isinstance(value, bool):
        return {"boolValue": value}
    elif isinstance(value, int):
        return {"intValue": value}
    elif isinstance(value, float):
        return {"doubleValue": value}
    else:
        return {"stringValue": str(value)}


def generate_trace_id() -> str:
    """Generate a new OpenTelemetry trace ID."""
    return os.urandom(16).hex()


def generate_span_id() -> str:
    """Generate a new OpenTelemetry span ID."""
    return os.urandom(8).hex()


@dataclass
class SpanContext:
    """Span context for tracking active spans."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None

    @classmethod
    def create_root_context(cls) -> "SpanContext":
        """Create a new root span context."""
        return cls(
            trace_id=generate_trace_id(),
            span_id=generate_span_id()
        )

    def create_child_context(self) -> "SpanContext":
        """Create a child span context."""
        return SpanContext(
            trace_id=self.trace_id,
            span_id=generate_span_id(),
            parent_span_id=self.span_id
        )
