"""
Logging utility module for Treebeard.

This module provides logging context management functionality,
allowing creation and management of trace contexts.
"""
import inspect
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from .context import LoggingContext
from .core import Treebeard
from .constants import TRACE_ID_KEY, MESSAGE_KEY, LEVEL_KEY, FILE_KEY, LINE_KEY


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

        frame = inspect.stack()[2]  # 0: this func, 1: SDK wrapper, 2: user
        filename = frame.filename
        line_number = frame.lineno

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

        # Create a new dictionary to avoid modifying in place
        processed_data = {}
        processed_data[FILE_KEY] = filename
        processed_data[LINE_KEY] = line_number

        masked_terms = {
            'password', 'pass', 'pw', 'secret', 'api_key', 'access_token', 'refresh_token',
            'token', 'key', 'auth', 'credentials', 'credential', 'private_key', 'public_key',
            'ssh_key', 'certificate', 'cert', 'signature', 'sign', 'hash', 'salt', 'nonce',
            'session_id', 'session', 'cookie', 'jwt', 'bearer', 'oauth', 'oauth2', 'openid',
            'client_id', 'client_secret', 'consumer_key', 'consumer_secret', 'aws_access_key',
            'aws_secret_key', 'aws_session_token', 'azure_key', 'gcp_key', 'api_secret',
            'encryption_key', 'decryption_key', 'master_key', 'root_key', 'admin_key',
            'database_password', 'db_password', 'db_pass', 'redis_password', 'redis_pass',
            'mongodb_password', 'mongodb_pass', 'postgres_password', 'postgres_pass',
            'mysql_password', 'mysql_pass', 'oracle_password', 'oracle_pass'
        }

        for key, value in log_data.items():
            if value is None:
                continue
            # Handle datetime objects
            if isinstance(value, datetime):
                processed_data[key] = int(value.timestamp())
            # Handle dictionaries
            elif isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, (int, float, str, bool, type(None))):
                        # Mask password-related keys
                        if any(pw_key in k.lower() for pw_key in masked_terms):
                            processed_data[f"{key}_{k}"] = '*****'
                        else:
                            processed_data[f"{key}_{k}"] = v
            # Handle objects
            elif isinstance(value, object) and not isinstance(value, (int, float, str, bool, type(None))):
                for attr_name in dir(value):
                    if not attr_name.startswith("_"):
                        try:
                            attr_value = getattr(value, attr_name)
                            if isinstance(attr_value, (int, float, str, bool, type(None))):
                                # Mask password-related keys
                                if any(pw_key in attr_name.lower() for pw_key in masked_terms):
                                    processed_data[f"{key}_{attr_name}"] = '*****'
                                else:
                                    processed_data[f"{key}_{attr_name}"] = attr_value
                        except:
                            continue
            # Keep all primitive types as is
            else:
                # Mask password-related keys
                if any(pw_key in key.lower() for pw_key in masked_terms):
                    processed_data[key] = '*****'
                else:
                    processed_data[key] = value

        return processed_data

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
