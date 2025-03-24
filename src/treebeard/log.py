"""
Logging utility module for Treebeard.

This module provides logging context management functionality,
allowing creation and management of trace contexts.
"""
import uuid
from typing import Optional, Dict, Any
from .context import LoggingContext
from .core import Treebeard


class Log:
    """Logging utility class for managing trace contexts."""

    TRACE_ID_KEY = "trace_id"

    @staticmethod
    def start(name: str) -> str:
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
        LoggingContext.set(Log.TRACE_ID_KEY, trace_id)
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
        log_data['message'] = message

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
        log_data['level'] = 'trace'
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
        log_data['level'] = 'debug'
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
        log_data['level'] = 'info'

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
        log_data['level'] = 'warning'
        Treebeard().add(log_data)

    @staticmethod
    def error(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log an error message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        log_data = Log._prepare_log_data(message, data, **kwargs)
        log_data['level'] = 'error'
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
        log_data['level'] = 'critical'
        Treebeard().add(log_data)
