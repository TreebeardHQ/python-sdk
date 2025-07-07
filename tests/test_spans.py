"""Tests for span functionality."""
import pytest
from unittest.mock import MagicMock, patch

from treebeardhq import Treebeard
from treebeardhq.span import start_span, end_span, span_context, get_current_span
from treebeardhq.spans import SpanKind, SpanStatus, SpanStatusCode
from treebeardhq.context import LoggingContext


@pytest.fixture
def reset_treebeard():
    """Reset Treebeard state between tests."""
    Treebeard.reset()
    LoggingContext.clear()
    LoggingContext.clear_span_stack()
    yield
    Treebeard.reset()
    LoggingContext.clear()
    LoggingContext.clear_span_stack()


class TestSpans:
    """Test span functionality."""

    def test_start_span_creates_span(self, reset_treebeard):
        """Test that start_span creates a span and adds it to context."""
        with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
            mock_exporter = MagicMock()
            MockExporter.return_value = mock_exporter
            
            Treebeard.init(api_key="test-key", endpoint="http://test.com")
            
            span = start_span("test_operation")
            
            assert span is not None
            assert span.name == "test_operation"
            assert span.kind == SpanKind.INTERNAL
            assert span.trace_id is not None
            assert span.span_id is not None
            assert not span.is_ended()
            
            # Check that span is in context
            current_span = LoggingContext.get_current_span()
            assert current_span == span

    def test_end_span_ends_current_span(self, reset_treebeard):
        """Test that end_span ends the current span."""
        with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
            mock_exporter = MagicMock()
            MockExporter.return_value = mock_exporter
            
            Treebeard.init(api_key="test-key", endpoint="http://test.com")
            
            span = start_span("test_operation")
            assert not span.is_ended()
            
            end_span()
            
            assert span.is_ended()
            # Span should be removed from context
            assert LoggingContext.get_current_span() is None

    def test_span_hierarchy(self, reset_treebeard):
        """Test parent-child span relationships."""
        with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
            mock_exporter = MagicMock()
            MockExporter.return_value = mock_exporter
            
            Treebeard.init(api_key="test-key", endpoint="http://test.com")
            
            parent_span = start_span("parent_operation")
            child_span = start_span("child_operation")
            
            assert child_span.parent_span_id == parent_span.span_id
            assert child_span.trace_id == parent_span.trace_id
            
            # Current span should be child
            assert LoggingContext.get_current_span() == child_span
            
            end_span()  # End child
            # Parent should be current again
            assert LoggingContext.get_current_span() == parent_span
            
            end_span()  # End parent
            assert LoggingContext.get_current_span() is None

    def test_span_context_manager(self, reset_treebeard):
        """Test span context manager."""
        with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
            mock_exporter = MagicMock()
            MockExporter.return_value = mock_exporter
            
            Treebeard.init(api_key="test-key", endpoint="http://test.com")
            
            with span_context("test_operation") as span:
                assert span.name == "test_operation"
                assert not span.is_ended()
                assert LoggingContext.get_current_span() == span
            
            # Span should be ended and removed from context
            assert span.is_ended()
            assert LoggingContext.get_current_span() is None

    def test_span_context_manager_with_exception(self, reset_treebeard):
        """Test span context manager with exception."""
        with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
            mock_exporter = MagicMock()
            MockExporter.return_value = mock_exporter
            
            Treebeard.init(api_key="test-key", endpoint="http://test.com")
            
            with pytest.raises(ValueError):
                with span_context("test_operation") as span:
                    raise ValueError("test error")
            
            # Span should be ended with error status
            assert span.is_ended()
            assert span.status.code == SpanStatusCode.ERROR
            assert "test error" in span.status.message
            assert LoggingContext.get_current_span() is None

    def test_span_attributes_and_events(self, reset_treebeard):
        """Test span attributes and events."""
        with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
            mock_exporter = MagicMock()
            MockExporter.return_value = mock_exporter
            
            Treebeard.init(api_key="test-key", endpoint="http://test.com")
            
            span = start_span("test_operation", attributes={"key": "value"})
            span.set_attribute("another_key", "another_value")
            span.add_event("test_event", {"event_attr": "event_value"})
            
            assert span.attributes["key"] == "value"
            assert span.attributes["another_key"] == "another_value"
            assert len(span.events) == 1
            assert span.events[0].name == "test_event"
            assert span.events[0].attributes["event_attr"] == "event_value"
            
            end_span()

    def test_span_batching(self, reset_treebeard):
        """Test that spans are added to batch."""
        with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
            mock_exporter = MagicMock()
            MockExporter.return_value = mock_exporter
            
            Treebeard.init(api_key="test-key", endpoint="http://test.com")
            instance = Treebeard()
            
            # Mock the span batch to not trigger flush
            with patch.object(instance._span_batch, 'add', return_value=False) as mock_add:
                span = start_span("test_operation")
                end_span()
            
            # Check that span batch add was called
            mock_add.assert_called()

    def test_get_current_span_and_trace_id(self, reset_treebeard):
        """Test getting current span and trace ID."""
        with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
            mock_exporter = MagicMock()
            MockExporter.return_value = mock_exporter
            
            Treebeard.init(api_key="test-key", endpoint="http://test.com")
            
            # No span initially
            assert get_current_span() is None
            assert LoggingContext.get_trace_id() is None
            
            span = start_span("test_operation")
            
            # Should return current span and trace ID
            assert get_current_span() == span
            assert LoggingContext.get_trace_id() == span.trace_id
            
            end_span()
            
            # Should be None again
            assert get_current_span() is None
            assert LoggingContext.get_trace_id() is None