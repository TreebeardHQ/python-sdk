"""
Tests for the core functionality.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest

from treebeardhq.core import Treebeard
from treebeardhq.internal_utils.fallback_logger import fallback_logger


@pytest.fixture(autouse=True)
def reset_treebeard():
    """Reset Treebeard singleton between tests."""
    yield
    Treebeard.reset()


def test_init_valid_api_key():
    api_key = "test-api-key"
    Treebeard.init(api_key=api_key, endpoint="https://test.endpoint")
    client = Treebeard()
    assert client.api_key == api_key
    assert client._endpoint == "https://test.endpoint"


def test_singleton_behavior():
    api_key = "test-api-key"
    Treebeard.init(api_key=api_key,
                   endpoint="https://test.endpoint")

    instance1 = Treebeard()
    instance2 = Treebeard()

    assert instance1 is instance2
    assert instance1.api_key == instance2.api_key == api_key


def test_init_empty_api_key(caplog):
    """Test that empty API key triggers fallback logging."""
    caplog.set_level(logging.WARNING)

    with patch("logging.StreamHandler.emit") as mock_emit:

        # Test with empty string
        Treebeard.reset()
        Treebeard.init(api_key="")
        instance = Treebeard()
        assert instance._using_fallback is True
        assert mock_emit.call_count == 1
        assert "No API key provided" in mock_emit.call_args[0][0].msg


def test_init_invalid_api_key_type():
    with pytest.raises(ValueError, match="API key must be a string"):
        Treebeard.init(api_key=123, endpoint="https://test.endpoint")


def test_uninitialized_client():
    Treebeard.init()
    instance = Treebeard()
    assert instance._api_key is None


def test_fallback_logger_level():
    """Test that fallback logger is configured with NOTSET level."""
    assert fallback_logger.level == logging.INFO


def test_switching_between_modes(reset_treebeard):
    """Test switching between fallback and API modes."""
    # Start with fallback mode
    Treebeard.init()
    instance = Treebeard()
    assert instance._using_fallback is True

    # Reset and switch to API mode
    Treebeard.reset()
    Treebeard.init(api_key="test-key", endpoint="http://test.com")
    instance = Treebeard()
    assert instance._using_fallback is False

    # Verify API mode is properly configured
    assert instance._api_key == "test-key"
    assert instance._endpoint == "http://test.com"


def test_project_name_initialization(reset_treebeard):
    """Test that project_name is properly set and sent to API."""
    project_name = "test-project"
    
    # Mock the TreebeardExporter class
    with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
        # Create a mock exporter instance
        mock_exporter = MagicMock()
        MockExporter.return_value = mock_exporter
        
        # Initialize with project_name
        Treebeard.init(project_name=project_name,
                       api_key="test-key", endpoint="http://test.com")
        instance = Treebeard()

        # Verify project_name is set
        assert instance._project_name == project_name
        
        # Verify exporter was initialized with correct parameters
        MockExporter.assert_called_once_with(
            api_key="test-key",
            endpoint="http://test.com",
            objects_endpoint="http://test.com",
            spans_endpoint="http://test.com",
            project_name=project_name
        )

        # Add a log entry to trigger sending
        instance.add({'level': 'info', 'message': 'test'})
        instance.flush()

        # Verify the exporter's send_logs_async was called
        assert mock_exporter.send_logs_async.called
        call_args = mock_exporter.send_logs_async.call_args
        logs = call_args[0][0]  # First positional argument
        config_version = call_args[0][1]  # Second positional argument
        update_callback = call_args[0][2]  # Third positional argument
        
        assert len(logs) == 1
        assert update_callback == instance.update_project_config


def test_project_name_not_overwritten_on_reinitialization(reset_treebeard):
    """Test that project_name can be updated on subsequent init calls."""
    # First initialization
    Treebeard.init(project_name="first-project",
                   api_key="test-key", endpoint="http://test.com")
    instance = Treebeard()
    assert instance._project_name == "first-project"

    # Second initialization with different project_name (should update)
    Treebeard.init(project_name="second-project")
    assert instance._project_name == "second-project"


def test_project_name_none_when_not_provided(reset_treebeard):
    """Test that project_name is None when not provided during initialization."""
    # Mock the TreebeardExporter class
    with patch('treebeardhq.core.TreebeardExporter') as MockExporter:
        # Create a mock exporter instance
        mock_exporter = MagicMock()
        MockExporter.return_value = mock_exporter
        
        Treebeard.init(api_key="test-key", endpoint="http://test.com")
        instance = Treebeard()

        # Should be None when not provided
        assert instance._project_name is None
        
        # Verify exporter was initialized with None project_name
        MockExporter.assert_called_once_with(
            api_key="test-key",
            endpoint="http://test.com",
            objects_endpoint="http://test.com",
            spans_endpoint="http://test.com",
            project_name=None
        )

        # Add a log entry to trigger sending
        instance.add({'level': 'info', 'message': 'test'})
        instance.flush()

        # Verify the exporter's send_logs_async was called
        assert mock_exporter.send_logs_async.called


def test_project_name_reset(reset_treebeard):
    """Test that project_name is properly reset."""
    # Initialize with project_name
    Treebeard.init(project_name="test-project",
                   api_key="test-key", endpoint="http://test.com")
    instance = Treebeard()
    assert instance._project_name == "test-project"

    # Reset should clear project_name
    Treebeard.reset()

    # New instance should have None project_name
    Treebeard.init(api_key="test-key", endpoint="http://test.com")
    instance = Treebeard()
    assert instance._project_name is None


def test_project_name_reset_on_reinit(reset_treebeard):
    """Test the original bug scenario where project_name gets sent as None to API."""
    # This test reproduces the original issue described by the user

    # Initialize Treebeard with a project name
    Treebeard.init(project_name="my-project",
                   api_key="test-key", endpoint="http://test.com")
    instance = Treebeard()

    # Verify initial project_name is correct
    assert instance._project_name == "my-project"

    # Simulate another initialization call (which could happen in some codebases)
    # Before the fix, this would cause project_name to be ignored due to early return
    Treebeard.init(api_key="test-key", endpoint="http://test.com")

    # After the fix,
    # project_name should still be "my-project"
    # since no new project_name was provided
    assert instance._project_name == "my-project"

    # Now test with a different project name - should update
    Treebeard.init(project_name="updated-project")
    assert instance._project_name == "updated-project"


def test_otel_format_initialization(reset_treebeard):
    """Test that OpenTelemetry format can be enabled during initialization."""
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test.com",
        otel_format=True
    )
    instance = Treebeard()

    assert instance._otel_format is True


def test_otel_format_defaults_to_false(reset_treebeard):
    """Test that OpenTelemetry format defaults to False."""
    Treebeard.init(api_key="test-key", endpoint="http://test.com")
    instance = Treebeard()

    assert instance._otel_format is False


def test_otel_format_basic_log(reset_treebeard):
    """Test basic OpenTelemetry log formatting."""
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test.com",
        project_name="test-project",
        otel_format=True
    )
    instance = Treebeard()

    # Create a test log entry
    log_entry = {
        'tb_rv2_trace_id': 'T123456789',
        'tb_rv2_message': 'Test message',
        'tb_rv2_level': 'info',
        'tb_rv2_file': '/path/to/file.py',
        'tb_rv2_line': 42,
        'tb_rv2_function': 'test_function',
        'tb_rv2_source': 'treebeard',
        'ts': 1634630400000
    }

    result = instance.format_otel(log_entry)

    # Verify OpenTelemetry structure
    assert result['TraceId'] == 'T123456789'
    assert result['Body'] == 'Test message'
    assert result['SeverityText'] == 'INFO'
    assert result['SeverityNumber'] == 9
    assert result['Timestamp'] == '1634630400000000000'  # nanoseconds

    # Verify Resource
    assert result['Resource']['service.name'] == 'test-project'
    assert result['Resource']['source'] == 'treebeard'

    # Verify InstrumentationScope
    assert result['InstrumentationScope']['Name'] == 'treebeard-python-sdk'
    assert result['InstrumentationScope']['Version'] == '2.0'

    # Verify Attributes
    assert result['Attributes']['code.filepath'] == '/path/to/file.py'
    assert result['Attributes']['code.lineno'] == 42
    assert result['Attributes']['code.function'] == 'test_function'


def test_otel_format_severity_mapping(reset_treebeard):
    """Test OpenTelemetry severity level mapping."""
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test.com",
        otel_format=True
    )
    instance = Treebeard()

    severity_tests = [
        ('trace', 'TRACE', 1),
        ('debug', 'DEBUG', 5),
        ('info', 'INFO', 9),
        ('warning', 'WARN', 13),
        ('error', 'ERROR', 17),
        ('critical', 'FATAL', 21)
    ]

    for level, expected_text, expected_number in severity_tests:
        log_entry = {
            'tb_rv2_level': level,
            'tb_rv2_message': f'Test {level} message'
        }

        result = instance.format_otel(log_entry)

        assert result['SeverityText'] == expected_text
        assert result['SeverityNumber'] == expected_number


def test_otel_format_with_exception(reset_treebeard):
    """Test OpenTelemetry formatting with exception information."""
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test.com",
        otel_format=True
    )
    instance = Treebeard()
    log_entry = {
        'tb_rv2_message': 'Error occurred',
        'tb_rv2_level': 'error',
        'tb_rv2_exec_type': 'ValueError',
        'tb_rv2_exec_value': 'Invalid value provided',
        'tb_rv2_traceback': (
            'Traceback (most recent call last):\n'
            '  File "test.py", line 1, in <module>\n'
            '    raise ValueError("Invalid value")\n'
            'ValueError: Invalid value'
        )
    }

    result = instance.format_otel(log_entry)

    # Verify exception attributes
    assert result['Attributes']['exception.type'] == 'ValueError'
    assert result['Attributes']['exception.message'] == 'Invalid value provided'
    assert 'Traceback (most recent call last)' in result['Attributes']['exception.stacktrace']


def test_otel_format_with_trace_name(reset_treebeard):
    """Test OpenTelemetry formatting with trace name."""
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test.com",
        otel_format=True
    )
    instance = Treebeard()

    log_entry = {
        'tb_rv2_message': 'Test trace',
        'tb_rv2_trace_name': 'user_login_flow'
    }

    result = instance.format_otel(log_entry)

    assert result['Attributes']['trace.name'] == 'user_login_flow'


def test_otel_format_with_additional_attributes(reset_treebeard):
    """Test OpenTelemetry formatting preserves additional attributes."""
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test.com",
        otel_format=True
    )
    instance = Treebeard()

    log_entry = {
        'tb_rv2_message': 'HTTP request',
        'user_id': '12345',
        'request_id': 'req_abc123',
        'http_method': 'POST',
        'status_code': 200
    }

    result = instance.format_otel(log_entry)

    # Verify additional attributes are preserved
    assert result['Attributes']['user_id'] == '12345'
    assert result['Attributes']['request_id'] == 'req_abc123'
    assert result['Attributes']['http_method'] == 'POST'
    assert result['Attributes']['status_code'] == 200


def test_format_log_uses_otel_when_enabled(reset_treebeard):
    """Test that format_log uses OpenTelemetry format when enabled."""
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test.com",
        otel_format=True
    )
    instance = Treebeard()

    log_entry = {
        'tb_rv2_message': 'Test message',
        'tb_rv2_level': 'info'
    }

    # format_log should use OTel format
    otel_result = instance.format_log(log_entry.copy())

    # Should have OTel structure
    assert 'Body' in otel_result
    assert 'SeverityText' in otel_result
    assert 'InstrumentationScope' in otel_result


def test_format_log_uses_standard_when_disabled(reset_treebeard):
    """Test that format_log uses standard format when OTel is disabled."""
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test.com",
        otel_format=False
    )
    instance = Treebeard()

    log_entry = {
        'tb_rv2_message': 'Test message',
        'tb_rv2_level': 'info'
    }

    # format_log should use standard format
    standard_result = instance.format_log(log_entry.copy())

    # Should have standard structure
    assert 'msg' in standard_result
    assert 'lvl' in standard_result
    assert 'ts' in standard_result
