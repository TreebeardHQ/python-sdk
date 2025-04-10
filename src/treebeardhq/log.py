"""
Logging utility module for Treebeard.

This module provides logging context management functionality,
allowing creation and management of trace contexts.
"""
import uuid
from typing import Optional, Dict, Any
from .context import LoggingContext
from .core import Treebeard
from .constants import TRACE_ID_KEY, MESSAGE_KEY, LEVEL_KEY, ERROR_KEY, TS_KEY


class Log:
    """Logging utility class for managing trace contexts."""

    @staticmethod
    def start(name: Optional[str] = None) -> str:
        """Start a new logging context with the given name.

        If a context already exists, it will be cleared before creating
        the new one.

        Args:
            name: The name of the logging context

        Returns:
            The generated trace ID
        """
        # Clear any existing context
        Log.end()

        # Generate new trace ID
        trace_id = f"T{uuid.uuid4().hex}"

        # Set up new context
        LoggingContext.set(TRACE_ID_KEY, trace_id)

        if name:
            LoggingContext.set("name", name)

        return trace_id

    @staticmethod
    def end() -> None:
        """End the current logging context by clearing all context data."""
        LoggingContext.clear()

    @staticmethod
    def _prepare_log_data(message: str, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Prepare log data by merging context, provided data and kwargs.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments

        Returns:
            Dict containing the complete log entry
        """
        # Start with the context data
        log_data = LoggingContext.get_all()

        # Add the message
        log_data[MESSAGE_KEY] = message

        if not log_data.get(TRACE_ID_KEY):
            trace_id = Log.start()
            log_data[TRACE_ID_KEY] = trace_id

        # Merge explicit data dict if provided
        if data is not None:
            log_data.update(data)

        # Merge kwargs
        if kwargs:
            log_data.update(kwargs)

        return log_data

    @staticmethod
    def trace(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a trace message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        log_data = Log._prepare_log_data(message, data, **kwargs)
        log_data[LEVEL_KEY] = 'trace'
        Treebeard().add(log_data)

    @staticmethod
    def debug(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a debug message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        log_data = Log._prepare_log_data(message, data, **kwargs)
        log_data[LEVEL_KEY] = 'debug'
        Treebeard().add(log_data)

    @staticmethod
    def info(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log an info message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        log_data = Log._prepare_log_data(message, data, **kwargs)
        log_data[LEVEL_KEY] = 'info'

        Treebeard().add(log_data)

    @staticmethod
    def warning(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a warning message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        log_data = Log._prepare_log_data(message, data, **kwargs)
        log_data[LEVEL_KEY] = 'warning'
        Treebeard().add(log_data)

    @staticmethod
    def warn(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """alias for warning

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        Log.warning(message, data, **kwargs)

    @staticmethod
    def error(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log an error message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        log_data = Log._prepare_log_data(message, data, **kwargs)
        log_data[LEVEL_KEY] = 'error'
        Treebeard().add(log_data)

    @staticmethod
    def critical(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a critical message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        log_data = Log._prepare_log_data(message, data, **kwargs)
        log_data[LEVEL_KEY] = 'critical'
        Treebeard().add(log_data)
