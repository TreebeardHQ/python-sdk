"""
Tests for the core functionality.
"""
import pytest
import logging
from unittest.mock import patch, MagicMock
from treebeard.core import Treebeard, fallback_logger
from treebeard.utils import ThreadingMode


@pytest.fixture(autouse=True)
def reset_treebeard():
    """Reset Treebeard singleton between tests."""
    yield
    Treebeard.reset()


def test_init_valid_api_key():
    api_key = "test-api-key"
    Treebeard.init(api_key, endpoint="https://test.endpoint")
    client = Treebeard()
    assert client.api_key == api_key
    assert client.endpoint == "https://test.endpoint"
    assert client.debug_mode is False  # default value


def test_init_with_config():
    api_key = "test-api-key"
    Treebeard.init(
        api_key,
        endpoint="https://test.endpoint",
        debug_mode=True,
        batch_size=200,
        batch_age=10.0
    )
    client = Treebeard()
    assert client.api_key == api_key
    assert client.endpoint == "https://test.endpoint"
    assert client.debug_mode is True


def test_singleton_behavior():
    api_key = "test-api-key"
    Treebeard.init(api_key, endpoint="https://test.endpoint", debug_mode=True)

    instance1 = Treebeard()
    instance2 = Treebeard()

    assert instance1 is instance2
    assert instance1.api_key == instance2.api_key == api_key
    assert instance1.debug_mode == instance2.debug_mode is True


def test_prevent_double_init():
    Treebeard.init("first-key", endpoint="https://test.endpoint")
    with pytest.raises(RuntimeError, match="Treebeard is already initialized"):
        Treebeard.init(
            "second-key", endpoint="https://test.endpoint", debug_mode=True)


def test_init_empty_api_key(caplog):
    """Test that empty API key triggers fallback logging."""
    caplog.set_level(logging.WARNING)

    # Test with empty string
    Treebeard.reset()
    Treebeard.init("")
    instance = Treebeard()
    assert instance._using_fallback is True
    assert "No API key provided" in caplog.text

    # Test with whitespace
    Treebeard.reset()
    Treebeard.init("   ")
    instance = Treebeard()
    assert instance._using_fallback is True
    assert "No API key provided" in caplog.text


def test_init_invalid_api_key_type():
    with pytest.raises(ValueError, match="API key must be a string"):
        Treebeard.init(123, endpoint="https://test.endpoint")


def test_uninitialized_client():
    client = Treebeard()
    assert client.api_key is None
    assert client.debug_mode is False
    assert client.endpoint is None


def test_config_boolean_coercion():
    """Test that debug_mode is coerced to boolean."""
    Treebeard.init("test-key", endpoint="https://test.endpoint", debug_mode=1)
    assert Treebeard().debug_mode is True

    Treebeard.reset()
    Treebeard.init("test-key", endpoint="https://test.endpoint", debug_mode="")
    assert Treebeard().debug_mode is False


def test_init_missing_endpoint():
    with pytest.raises(ValueError, match="endpoint must be provided"):
        Treebeard.init("test-key")


def test_init_with_api_key(reset_treebeard):
    """Test initialization with API key."""
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test.com",
        debug_mode=True
    )
    instance = Treebeard()

    assert instance.api_key == "test-key"
    assert instance.endpoint == "http://test.com"
    assert instance.debug_mode is True
    assert instance._using_fallback is False


def test_init_without_api_key(reset_treebeard, caplog):
    """Test initialization without API key falls back to standard logging."""
    caplog.set_level(logging.WARNING)

    Treebeard.init()
    instance = Treebeard()

    assert instance._using_fallback is True
    assert instance.api_key is None
    assert "No API key provided" in caplog.text


def test_fallback_logger_level():
    """Test that fallback logger is configured with NOTSET level."""
    assert fallback_logger.level == logging.NOTSET


def test_log_to_fallback(reset_treebeard, caplog):
    """Test logging to fallback logger with different log levels."""
    # Set log level to DEBUG to capture all messages
    caplog.set_level(logging.DEBUG)

    Treebeard.init()
    instance = Treebeard()

    # Clear the initialization warning
    caplog.clear()

    test_entry = {
        'level': 'info',
        'message': 'Test message',
        'metadata': 'test'
    }

    with patch('treebeard.core.colored') as mock_colored:
        mock_colored.side_effect = lambda text, color: text
        instance.add(test_entry)

    assert 'Test message' in caplog.text
    assert 'metadata' in caplog.text


def test_fallback_logger_colors():
    """Test that correct colors are mapped to log levels."""
    from treebeard.core import LEVEL_COLORS

    assert LEVEL_COLORS['debug'] == 'grey'
    assert LEVEL_COLORS['info'] == 'green'
    assert LEVEL_COLORS['warning'] == 'yellow'
    assert LEVEL_COLORS['error'] == 'red'
    assert LEVEL_COLORS['critical'] == 'red'


def test_complex_metadata_formatting(reset_treebeard, caplog):
    """Test that complex metadata is properly formatted in fallback logs."""
    # Set log level to DEBUG to capture all messages
    caplog.set_level(logging.DEBUG)

    Treebeard.init()
    instance = Treebeard()

    # Clear the initialization warning
    caplog.clear()

    test_entry = {
        'level': 'info',
        'message': 'Test message',
        'nested': {
            'key1': 'value1',
            'key2': ['list', 'of', 'items']
        }
    }

    with patch('treebeard.core.colored') as mock_colored:
        mock_colored.side_effect = lambda text, color: text
        instance.add(test_entry)

    assert 'Test message' in caplog.text
    assert "'key1': 'value1'" in caplog.text
    assert "['list', 'of', 'items']" in caplog.text


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
    assert instance.api_key == "test-key"
    assert instance.endpoint == "http://test.com"


def test_fallback_mode_ignores_batch(reset_treebeard):
    """Test that fallback mode doesn't create or use batch."""
    Treebeard.init()
    instance = Treebeard()

    assert instance._batch is None

    # Adding logs shouldn't create a batch
    test_entry = {
        'level': 'info',
        'message': 'Test message'
    }
    instance.add(test_entry)

    assert instance._batch is None


def test_api_key_without_endpoint(reset_treebeard):
    """Test that providing API key without endpoint raises error."""
    with pytest.raises(ValueError) as exc_info:
        Treebeard.init(api_key="test-key")

    assert "endpoint must be provided" in str(exc_info.value)


def test_debug_mode_with_fallback(reset_treebeard, caplog):
    """Test debug mode works with fallback logger."""
    Treebeard.init(debug_mode=True)
    instance = Treebeard()

    assert instance.debug_mode is True
    assert instance._using_fallback is True
