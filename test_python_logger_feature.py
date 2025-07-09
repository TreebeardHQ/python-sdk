#!/usr/bin/env python3
"""
Manual test script for the Python logger integration feature.
"""

import logging

from treebeardhq.core import Treebeard
from treebeardhq.log import Log


def test_basic_functionality():
    """Test basic Python logger forwarding functionality."""
    print("=== Testing Basic Python Logger Forwarding ===")

    # Initialize Treebeard with Python logger capture enabled
    Treebeard.reset()
    Treebeard.init(
        api_key="test-key",
        endpoint="http://test-endpoint.com",
        capture_python_logger=True,
        python_logger_level="DEBUG"
    )

    # Create a logger and test different log levels
    test_logger = logging.getLogger("test.module")

    print("Logging messages at different levels...")
    test_logger.debug("Debug message")
    test_logger.info("Info message with data: %s", {"user_id": 123})
    test_logger.warning("Warning message")
    test_logger.error("Error message")

    print("Done!")


def test_exception_handling():
    """Test Python logger forwarding with exceptions."""
    print("\n=== Testing Exception Handling ===")

    logger = logging.getLogger("error.handler")

    try:
        # Simulate an error
        _result = 1 / 0
    except ZeroDivisionError:
        logger.error("Division by zero occurred", exc_info=True)

    print("Exception logged!")


def test_manual_enable_disable():
    """Test manual enable/disable of Python logger forwarding."""
    print("\n=== Testing Manual Enable/Disable ===")

    # Reset to clean state
    Treebeard.reset()
    Treebeard.init(api_key="test-key")

    logger = logging.getLogger("manual.test")

    print("Python logger forwarding disabled:")
    print(f"Is enabled: {Log.is_python_logger_forwarding_enabled()}")
    logger.info("This should not be forwarded")

    print("\nEnabling Python logger forwarding...")
    Log.enable_python_logger_forwarding(level=logging.INFO)
    print(f"Is enabled: {Log.is_python_logger_forwarding_enabled()}")
    logger.info("This should be forwarded")

    print("\nDisabling Python logger forwarding...")
    Log.disable_python_logger_forwarding()
    print(f"Is enabled: {Log.is_python_logger_forwarding_enabled()}")
    logger.info("This should not be forwarded again")


if __name__ == "__main__":
    test_basic_functionality()
    test_with_trace_context()
    test_exception_handling()
    test_manual_enable_disable()

    print("\n=== All tests completed! ===")
