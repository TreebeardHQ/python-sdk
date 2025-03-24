"""Tests for the Log class functionality."""
import pytest
from treebeard.log import Log
from treebeard.core import Treebeard
from treebeard.context import LoggingContext
import logging
from unittest.mock import patch, MagicMock


@pytest.fixture
def treebeard():
    """Setup and teardown for Treebeard instance."""
    Treebeard.init(api_key="test-key", endpoint="http://test.com")
    yield Treebeard()
    Treebeard.reset()
    LoggingContext.clear()


def test_start_creates_trace_context():
    """Test that start() creates a new trace context with correct data."""
    trace_id = Log.start("test-trace")

    assert trace_id.startswith("T")  # Trace ID format check
    assert len(trace_id) == 33  # "T" + 32 char UUID

    context = LoggingContext.get_all()
    assert context["trace_id"] == trace_id
    assert context["name"] == "test-trace"


def test_end_clears_context():
    """Test that end() clears the trace context."""
    Log.start("test-trace")
    Log.end()

    assert LoggingContext.get_all() == {}


def test_log_with_context(treebeard, mocker):
    """Test logging with context data."""
    mock_add = mocker.patch.object(treebeard, 'add')

    trace_id = Log.start("test-trace")
    Log.info("Test message")

    mock_add.assert_called_once()
    log_data = mock_add.call_args[0][0]
    assert log_data["message"] == "Test message"
    assert log_data["level"] == "info"
    assert log_data["trace_id"] == trace_id
    assert log_data["name"] == "test-trace"


def test_log_with_data_dict(treebeard, mocker):
    """Test logging with additional data dictionary."""
    mock_add = mocker.patch.object(treebeard, 'add')

    Log.error("Error occurred", {"error_code": 500, "service": "auth"})

    mock_add.assert_called_once()
    log_data = mock_add.call_args[0][0]
    assert log_data["message"] == "Error occurred"
    assert log_data["level"] == "error"
    assert log_data["error_code"] == 500
    assert log_data["service"] == "auth"


def test_log_with_kwargs(treebeard, mocker):
    """Test logging with keyword arguments."""
    mock_add = mocker.patch.object(treebeard, 'add')

    Log.warning("Resource low", cpu_usage=90, memory=95)

    mock_add.assert_called_once()
    log_data = mock_add.call_args[0][0]
    assert log_data["message"] == "Resource low"
    assert log_data["level"] == "warning"
    assert log_data["cpu_usage"] == 90
    assert log_data["memory"] == 95


def test_log_with_both_data_and_kwargs(treebeard, mocker):
    """Test logging with both data dict and kwargs."""
    mock_add = mocker.patch.object(treebeard, 'add')

    Log.debug(
        "Debug info",
        {"component": "database"},
        query_time=15.3
    )

    mock_add.assert_called_once()
    log_data = mock_add.call_args[0][0]
    assert log_data["message"] == "Debug info"
    assert log_data["level"] == "debug"
    assert log_data["component"] == "database"
    assert log_data["query_time"] == 15.3


def test_log_levels(treebeard, mocker):
    """Test all log levels."""
    mock_add = mocker.patch.object(treebeard, 'add')

    levels = ['trace', 'debug', 'info', 'warning', 'error', 'critical']

    for level in levels:
        log_method = getattr(Log, level)
        log_method(f"{level} message")

        mock_add.assert_called()
        log_data = mock_add.call_args[0][0]
        assert log_data["level"] == level
        assert log_data["message"] == f"{level} message"

        mock_add.reset_mock()


def test_nested_contexts():
    """Test that starting a new context clears the previous one."""
    first_trace = Log.start("first")
    first_context = LoggingContext.get_all()

    second_trace = Log.start("second")
    second_context = LoggingContext.get_all()

    assert first_trace != second_trace
    assert first_context != second_context
    assert second_context["name"] == "second"


def test_fallback_logger_initialization():
    """Test that Treebeard initializes correctly without an API key."""
    # Reset Treebeard singleton
    Treebeard.reset()

    # Initialize without API key
    Treebeard.init()

    instance = Treebeard()
    assert instance._using_fallback == True
    assert instance._api_key is None


@pytest.fixture
def mock_colored():
    with patch('treebeard.core.colored') as mock:
        # Make colored function just return the input string
        mock.side_effect = lambda text, color: text
        yield mock


@pytest.fixture
def captured_logs(caplog):
    """Fixture to capture logs with proper level."""
    caplog.set_level(logging.DEBUG)
    return caplog


def test_fallback_logging(captured_logs, mock_colored):
    """Test that logs are correctly sent to the fallback logger."""
    # Reset and initialize without API key
    Treebeard.reset()
    Treebeard.init()

    # Clear any initialization messages
    captured_logs.clear()

    # Start a trace context
    trace_id = Log.start("test_context")

    # Test different log levels
    Log.debug("Debug message", extra_field="debug_value")
    Log.info("Info message", extra_field="info_value")
    Log.warning("Warning message", extra_field="warning_value")
    Log.error("Error message", extra_field="error_value")

    # Verify logs were captured with correct levels
    assert len(captured_logs.records) == 4

    # Check debug message
    assert "Debug message" in captured_logs.records[0].message
    assert captured_logs.records[0].levelno == logging.DEBUG
    assert "debug_value" in captured_logs.records[0].message
    assert trace_id in captured_logs.records[0].message

    # Check info message
    assert "Info message" in captured_logs.records[1].message
    assert captured_logs.records[1].levelno == logging.INFO

    # Check warning message
    assert "Warning message" in captured_logs.records[2].message
    assert captured_logs.records[2].levelno == logging.WARNING

    # Check error message
    assert "Error message" in captured_logs.records[3].message
    assert captured_logs.records[3].levelno == logging.ERROR


def test_fallback_metadata_formatting(captured_logs, mock_colored):
    """Test that metadata is properly formatted in fallback logs."""
    Treebeard.reset()
    Treebeard.init()

    # Clear any initialization messages
    captured_logs.clear()

    complex_metadata = {
        "nested": {
            "field1": "value1",
            "field2": ["list", "of", "values"]
        },
        "simple": "value"
    }

    Log.info("Message with complex metadata", data=complex_metadata)

    # Verify the log was captured
    assert len(captured_logs.records) == 1
    log_message = captured_logs.records[0].message

    # Check that the message and metadata are present
    assert "Message with complex metadata" in log_message
    assert "field1': 'value1'" in log_message
    assert "field2': ['list', 'of', 'values']" in log_message
    assert "simple': 'value'" in log_message


def test_switching_to_api_logging():
    """Test that providing API key switches to API logging mode."""
    Treebeard.reset()

    # First initialize without API key
    Treebeard.init()
    assert Treebeard()._using_fallback == True

    # Reset and initialize with API key
    Treebeard.reset()
    Treebeard.init(api_key="test_key", endpoint="http://test.endpoint")

    instance = Treebeard()
    assert instance._using_fallback == False
    assert instance._api_key == "test_key"
    assert instance.endpoint == "http://test.endpoint"
