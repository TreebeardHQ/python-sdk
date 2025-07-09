"""Tests for the Log class functionality."""
import logging
from unittest.mock import patch

import pytest

from treebeardhq.constants import (
    EXEC_TYPE_RESERVED_V2,
    EXEC_VALUE_RESERVED_V2,
    LEVEL_KEY_RESERVED_V2,
    MESSAGE_KEY_RESERVED_V2,
    SOURCE_KEY_RESERVED_V2,
    TRACE_ID_KEY_RESERVED_V2,
    TRACE_NAME_KEY_RESERVED_V2,
    TRACEBACK_KEY_RESERVED_V2,
)
from treebeardhq.context import LoggingContext
from treebeardhq.core import Treebeard
from treebeardhq.log import Log


@pytest.fixture
def treebeard():
    """Setup and teardown for Treebeard instance."""
    Treebeard.init(api_key="test-key", endpoint="http://test.com")
    yield Treebeard()
    Treebeard.reset()
    LoggingContext.clear()


def test_log_with_data_dict(treebeard, mocker):
    """Test logging with additional data dictionary."""
    mock_add = mocker.patch.object(treebeard, 'add')

    Log.error("Error occurred", {"error_code": 500, "service": "auth"})

    assert mock_add.call_count == 2  # Assert it was called twice
    log_data = mock_add.call_args_list[1][0][0]
    assert log_data[MESSAGE_KEY_RESERVED_V2] == "Error occurred"


def test_log_with_kwargs(treebeard, mocker):
    """Test logging with keyword arguments."""
    mock_add = mocker.patch.object(treebeard, 'add')

    Log.warning("Resource low", cpu_usage=90, memory=95)

    assert mock_add.call_count == 2  # Assert it was called twice
    log_data = mock_add.call_args_list[1][0][0]
    assert log_data[MESSAGE_KEY_RESERVED_V2] == "Resource low"
    assert log_data[LEVEL_KEY_RESERVED_V2] == "warning"
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

    assert mock_add.call_count == 2  # Assert it was called twice
    log_data = mock_add.call_args_list[1][0][0]
    assert log_data[MESSAGE_KEY_RESERVED_V2] == "Debug info"
    assert log_data[LEVEL_KEY_RESERVED_V2] == "debug"
    assert log_data["component"] == "database"
    assert log_data["query_time"] == 15.3


def test_log_levels(treebeard, mocker):
    """Test all log levels."""
    mock_add = mocker.patch.object(treebeard, 'add')

    levels = ['debug', 'info',
              'warning', 'error']

    for level in levels:
        log_method = getattr(Log, level)
        log_method(f"{level} message")

        mock_add.assert_called()
        log_data = mock_add.call_args[0][0]
        assert log_data[LEVEL_KEY_RESERVED_V2] == level
        assert log_data[MESSAGE_KEY_RESERVED_V2] == f"{level} message"

        mock_add.reset_mock()


@pytest.fixture
def mock_colored():
    with patch('treebeardhq.core.colored') as mock:
        # Make colored function just return the input string
        mock.side_effect = lambda text, color: text
        yield mock


@pytest.fixture
def captured_logs(caplog):
    """Fixture to capture logs with proper level."""
    caplog.set_level(logging.DEBUG)
    return caplog


def test_fallback_metadata_formatting(captured_logs, mock_colored):
    """Test that metadata is properly formatted in fallback logs."""
    Treebeard.reset()
    Treebeard.init()

    with patch("logging.StreamHandler.emit") as mock_emit:
        complex_metadata = {
            "nested": {
                "field1": "value1",
                "field2": ["list", "of", "values"]
            },
            "simple": "value"
        }

        Log.info("Message with complex metadata", data=complex_metadata)

        # Verify the log was captured
        assert mock_emit.call_count == 2
        log_message = mock_emit.call_args_list[1][0][0].msg

        # Check that the message and metadata are present
        assert "Message with complex metadata" in log_message
        assert 'field1": "value1"' in log_message
        assert 'field2_count": 3' in log_message
        assert 'simple": "value"' in log_message


def test_switching_to_api_logging():
    """Test that providing API key switches to API logging mode."""
    Treebeard.reset()

    # First initialize without API key
    Treebeard.init()
    assert Treebeard()._using_fallback

    # Reset and initialize with API key
    Treebeard.reset()
    Treebeard.init(api_key="test_key", endpoint="http://test.endpoint")

    instance = Treebeard()
    assert not instance._using_fallback
    assert instance._api_key == "test_key"
    assert instance._endpoint == "http://test.endpoint"


def test_python_logger_forwarding_basic(treebeard, mocker):
    """Test basic Python logger forwarding functionality."""
    # Ensure clean state
    Log.disable_python_logger_forwarding()
    LoggingContext.clear()

    mock_add = mocker.patch.object(treebeard, 'add')

    # Enable Python logger forwarding
    Log.enable_python_logger_forwarding(level=logging.DEBUG)

    # Create a logger and log messages
    test_logger = logging.getLogger("test_logger")
    test_logger.info("Test message from Python logger")

    # Verify the message was captured
    # Note: We expect 2 calls - one for auto-created trace start, one for the actual message
    assert mock_add.call_count == 2
    calls = mock_add.call_args_list

    # The second call should be our Python logger message
    log_data = calls[1][0][0]
    assert log_data[MESSAGE_KEY_RESERVED_V2] == "Test message from Python logger"
    assert log_data[LEVEL_KEY_RESERVED_V2] == "info"
    assert log_data[SOURCE_KEY_RESERVED_V2] == "python_logger"
    assert log_data["logger_name"] == "test_logger"

    # Clean up
    Log.disable_python_logger_forwarding()


def test_python_logger_forwarding_with_args(treebeard, mocker):
    """Test Python logger forwarding with message arguments."""
    # Ensure clean state
    Log.disable_python_logger_forwarding()
    LoggingContext.clear()

    mock_add = mocker.patch.object(treebeard, 'add')

    Log.enable_python_logger_forwarding()

    test_logger = logging.getLogger("test_logger")
    test_logger.warning("User %s failed login attempt %d", "john", 3)

    # Expect 2 calls - auto trace start + our message
    assert mock_add.call_count == 2
    log_data = mock_add.call_args_list[1][0][0]  # Get the second call
    assert log_data[MESSAGE_KEY_RESERVED_V2] == "User john failed login attempt 3"
    assert log_data[LEVEL_KEY_RESERVED_V2] == "warning"
    assert log_data["msg_template"] == "User %s failed login attempt %d"
    assert log_data["msg_args"] == ["john", "3"]

    Log.disable_python_logger_forwarding()


def test_python_logger_forwarding_with_exception(treebeard, mocker):
    """Test Python logger forwarding with exception information."""
    mock_add = mocker.patch.object(treebeard, 'add')

    Log.enable_python_logger_forwarding()

    test_logger = logging.getLogger("test_logger")

    try:
        raise ValueError("Test exception")
    except ValueError:
        test_logger.error("An error occurred", exc_info=True)

    assert mock_add.call_count == 2  # Assert it was called twice
    log_data = mock_add.call_args_list[1][0][0]
    assert log_data[MESSAGE_KEY_RESERVED_V2] == "An error occurred"
    assert log_data[LEVEL_KEY_RESERVED_V2] == "error"
    assert log_data[EXEC_TYPE_RESERVED_V2] == "ValueError"
    assert log_data[EXEC_VALUE_RESERVED_V2] == "Test exception"
    assert TRACEBACK_KEY_RESERVED_V2 in log_data
    assert "ValueError: Test exception" in log_data[TRACEBACK_KEY_RESERVED_V2]

    Log.disable_python_logger_forwarding()


def test_python_logger_forwarding_with_extra(treebeard, mocker):
    """Test Python logger forwarding with extra attributes."""
    mock_add = mocker.patch.object(treebeard, 'add')

    Log.enable_python_logger_forwarding()

    test_logger = logging.getLogger("test_logger")
    test_logger.info("User action", extra={
        "user_id": 123,
        "action": "login",
        "ip_address": "192.168.1.1"
    })

    assert mock_add.call_count == 2  # Assert it was called twice
    log_data = mock_add.call_args_list[1][0][0]
    assert log_data[MESSAGE_KEY_RESERVED_V2] == "User action"
    assert log_data[LEVEL_KEY_RESERVED_V2] == "info"
    assert log_data["user_id"] == 123
    assert log_data["action"] == "login"
    # Assert it was called twice
    assert log_data["ip_address"] == "192.168.1.1"

    Log.disable_python_logger_forwarding()


def test_python_logger_level_filtering(treebeard, mocker):
    """Test that Python logger level filtering works correctly."""
    # Ensure clean state
    Log.disable_python_logger_forwarding()
    LoggingContext.clear()

    mock_add = mocker.patch.object(treebeard, 'add')

    # Enable forwarding only for WARNING and above
    Log.enable_python_logger_forwarding(level=logging.WARNING)

    test_logger = logging.getLogger("test_logger")
    test_logger.debug("Debug message")  # Should not be captured
    test_logger.info("Info message")    # Should not be captured
    test_logger.warning("Warning message")  # Should be captured
    test_logger.error("Error message")   # Should be captured

    # Should have captured: auto trace start + WARNING + ERROR = 3 calls
    assert mock_add.call_count == 3

    # Check the captured messages (skip the first auto trace start)
    calls = mock_add.call_args_list
    assert calls[1][0][0][MESSAGE_KEY_RESERVED_V2] == "Warning message"
    assert calls[1][0][0][LEVEL_KEY_RESERVED_V2] == "warning"
    assert calls[2][0][0][MESSAGE_KEY_RESERVED_V2] == "Error message"
    assert calls[2][0][0][LEVEL_KEY_RESERVED_V2] == "error"

    Log.disable_python_logger_forwarding()


def test_python_logger_forwarding_enable_disable():
    """Test enabling and disabling Python logger forwarding."""
    # Ensure clean state
    Log.disable_python_logger_forwarding()

    # Initially should be disabled
    assert not Log.is_python_logger_forwarding_enabled()

    # Enable forwarding
    Log.enable_python_logger_forwarding()
    assert Log.is_python_logger_forwarding_enabled()

    # Disable forwarding
    Log.disable_python_logger_forwarding()
    assert not Log.is_python_logger_forwarding_enabled()


def test_treebeard_init_with_python_logger_capture():
    """Test Treebeard initialization with Python logger capture enabled."""
    Treebeard.reset()

    # Initialize with Python logger capture enabled
    Treebeard.init(
        api_key="test_key",
        capture_python_logger=True,
        python_logger_level="INFO"
    )

    instance = Treebeard()
    assert instance._capture_python_logger
    assert instance._python_logger_level == "INFO"

    # Should have enabled forwarding
    assert Log.is_python_logger_forwarding_enabled()

    # Clean up
    Log.disable_python_logger_forwarding()
    Treebeard.reset()


def test_python_logger_forwarding_without_trace_context(treebeard, mocker):
    """Test that Python logger messages get auto-assigned trace_id when no context exists."""
    mock_add = mocker.patch.object(treebeard, 'add')

    Log.enable_python_logger_forwarding()

    # Ensure no trace context exists
    LoggingContext.clear()

    # Log a message without trace context
    test_logger = logging.getLogger("no_trace_logger")
    test_logger.info("Message without trace context")

    # Verify the message got an auto-assigned trace_id
    mock_add.assert_called()
    log_data = mock_add.call_args[0][0]
    assert log_data[MESSAGE_KEY_RESERVED_V2] == "Message without trace context"
    assert TRACE_ID_KEY_RESERVED_V2 in log_data
    assert log_data[TRACE_ID_KEY_RESERVED_V2] is not None

    assert len(log_data[TRACE_ID_KEY_RESERVED_V2]) == 32  # 32 char UUID

    Log.disable_python_logger_forwarding()
