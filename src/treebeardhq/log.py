"""
Logging utility module for Treebeard.

This module provides logging context management functionality,
allowing creation and management of trace contexts.
"""
import asyncio
import inspect
import logging
import os
import re
import sys
import threading
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, TextIO, Type

from .constants import (
    EXEC_TYPE_RESERVED_V2,
    EXEC_VALUE_RESERVED_V2,
    FILE_KEY_RESERVED_V2,
    FUNCTION_KEY_RESERVED_V2,
    LEVEL_KEY_RESERVED_V2,
    LINE_KEY_RESERVED_V2,
    MESSAGE_KEY_RESERVED_V2,
    SOURCE_KEY_RESERVED_V2,
    SPAN_ID_KEY_RESERVED_V2,
    TAGS_KEY,
    TRACE_COMPLETE_ERROR_MARKER,
    TRACE_COMPLETE_SUCCESS_MARKER,
    TRACE_ID_KEY_RESERVED_V2,
    TRACE_NAME_KEY_RESERVED_V2,
    TRACE_START_MARKER,
    TRACEBACK_KEY_RESERVED_V2,
    TS_KEY,
)
from .context import LoggingContext
from .core import Treebeard
from .internal_utils.fallback_logger import sdk_logger

dev_logger = logging.getLogger("dev")

level_map = {
    logging.DEBUG: 'debug',
    logging.INFO: 'info',
    logging.WARNING: 'warning',
    logging.WARN: 'warning',  # deprecated but still used
    logging.ERROR: 'error',
    logging.CRITICAL: 'critical',
    logging.FATAL: 'critical'  # alias for CRITICAL
}


class TreebeardHandler(logging.Handler):
    """Custom logging handler that forwards Python logger messages to Treebeard."""

    def emit(self, record: logging.LogRecord) -> None:
        """
        Process and forward a log record to the Treebeard system.

        Args:
            record: The LogRecord instance containing log data
        """
        try:
            # Skip logs from the SDK itself to avoid infinite recursion
            if (
                'treebeard' in record.name.lower() or
                'treebeardhq' in record.pathname or
                record.name == 'treebeard.sdk'
            ):
                return

            # Map standard Python logging levels to Treebeard levels
            level_map = {
                logging.DEBUG: 'debug',
                logging.INFO: 'info',
                logging.WARNING: 'warning',
                logging.WARN: 'warning',  # deprecated but still used
                logging.ERROR: 'error',
                logging.CRITICAL: 'critical',
                logging.FATAL: 'critical'  # alias for CRITICAL
            }

            # Get the mapped level, default to 'info'
            treebeard_level = level_map.get(record.levelno, 'info')

            # Format the message (handles args formatting)
            message = record.getMessage()

            # Build metadata for the log entry
            metadata = {
                SOURCE_KEY_RESERVED_V2: "python_logger",
                'logger_name': record.name,
                'module': record.module,
                'process': record.process,
                'process_name': record.processName,
                'thread': record.thread,
                'thread_name': record.threadName,
                'relative_created': record.relativeCreated,
                'msecs': record.msecs,
                TS_KEY: round(record.created * 1000)  # Convert to milliseconds
            }

            # Handle original message template and args if available
            if hasattr(record, 'msg') and record.args:
                metadata['msg_template'] = str(record.msg)

                if type(record.args) == tuple:
                    metadata['msg_args'] = [str(arg) for arg in record.args]
                elif type(record.args) == dict:
                    metadata['params'] = record.args

            # Handle exception information
            if record.exc_info:
                exc_type, exc_value, exc_traceback = record.exc_info
                if exc_type and exc_value:
                    # Create an exception object to pass to Log methods
                    # This will be handled by _prepare_log_data's exception handling
                    metadata['error'] = exc_value

            # Handle explicit exception text
            if record.exc_text:
                metadata['exc_text'] = record.exc_text

            # Handle stack info
            if record.stack_info:
                metadata['stack_info'] = record.stack_info

            # Add any extra attributes from the log record
            # These would come from logger.info("msg", extra={"custom": "value"})
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created', 'msecs',
                    'relativeCreated', 'thread', 'threadName', 'processName', 'process',
                    'getMessage', 'exc_info', 'exc_text', 'stack_info', 'asctime', 'message'
                }:
                    metadata[key] = value

            # Send to Treebeard using the same path as other Log methods
            # This ensures consistent handling of trace_id, context, etc.
            log_method_map = {
                'debug': Log.debug,
                'info': Log.info,
                'warning': Log.warning,
                'error': Log.error,
                'critical': Log.critical
            }

            log_method = log_method_map.get(treebeard_level, Log.info)
            log_method(message, metadata)

        except Exception as e:
            # Don't let handler errors break the application
            sdk_logger.error(f"Error in TreebeardHandler: {str(e)}")


# Global handler instance
_treebeard_handler: Optional[TreebeardHandler] = None


masked_terms = {
    'password', 'pass', 'pw', 'secret', 'api_key', 'access_token', 'refresh_token',
    'token', 'auth', 'credentials', 'credential', 'private_key', 'public_key',
    'ssh_key', 'certificate', 'cert', 'signature', 'salt', 'nonce',
    'session_id', 'session', 'cookie', 'jwt', 'bearer', 'oauth', 'oauth2', 'openid',
    'client_id', 'client_secret', 'consumer_key', 'consumer_secret', 'aws_access_key',
    'aws_secret_key', 'aws_session_token', 'azure_key', 'gcp_key', 'api_secret',
    'encryption_key', 'decryption_key', 'master_key', 'root_key', 'admin_key',
    'database_password', 'db_password', 'db_pass', 'redis_password', 'redis_pass',
    'mongodb_password', 'mongodb_pass', 'postgres_password', 'postgres_pass',
    'mysql_password', 'mysql_pass', 'oracle_password', 'oracle_pass'
}

pattern = re.compile(
    r"(?P<db>[a-z\+]+)://(?P<user>[a-zA-Z0-9_-]+):(?P<pw>[a-zA-Z0-9_]+)@(?P<host>[\.a-zA-Z0-9_-]+):(?P<port>\d+)"
)


class Log:
    """Logging utility class for managing trace contexts and stdout override."""

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
        try:
            filename = None
            line_number = None
            function_name = None
            locals_dict = {}

            # don't take a frame from the SDK wrapper
            for frame_info in inspect.stack():
                frame_file = frame_info.filename
                if "treebeardhq" not in frame_file and "<frozen" not in frame_file:
                    filename = frame_file
                    line_number = frame_info.lineno
                    function_name = frame_info.function
                    # locals_dict = Log.extract_relevant_locals(
                    #     frame_info.frame.f_locals)
                    break

            # Start with the context data
            log_data = LoggingContext.get_all()

            # Add the message
            log_data[MESSAGE_KEY_RESERVED_V2] = message

            # log_data['f_locals'] = locals_dict

            # Merge explicit data dict if provided
            if data is not None and isinstance(data, dict):
                log_data.update(data)
            elif data is not None:
                log_data.update({'data': data})

            # Merge kwargs
            if kwargs:
                log_data.update(kwargs)

            # Create a new dictionary to avoid modifying in place
            processed_data = {}
            processed_data[FILE_KEY_RESERVED_V2] = filename
            processed_data[LINE_KEY_RESERVED_V2] = line_number
            processed_data[FUNCTION_KEY_RESERVED_V2] = function_name
            # if we haven't set the source upstream, it's from our SDK
            if not log_data.get(SOURCE_KEY_RESERVED_V2):
                log_data[SOURCE_KEY_RESERVED_V2] = "treebeard"

            for key, value in log_data.items():
                if value is None:
                    continue

                # sent from logger
                if key == 'msg_args':
                    processed_data[key] = value
                    continue

                # Handle exceptions - these get special treatment with traceback extraction
                if isinstance(value, Exception):
                    processed_data[EXEC_TYPE_RESERVED_V2] = value.__class__.__name__
                    processed_data[EXEC_VALUE_RESERVED_V2] = str(value)
                    if value.__traceback__ is not None:
                        processed_data[TRACEBACK_KEY_RESERVED_V2] = '\n'.join(traceback.format_exception(
                            type(value), value, value.__traceback__))

                # Handle datetime objects - convert to timestamp
                elif isinstance(value, datetime):
                    processed_data[key] = int(value.timestamp())
                # Handle dictionaries - maintain their nested structure
                elif isinstance(value, dict):
                    processed_data[key] = {}
                    Log.recurse_and_collect_dict(value, processed_data[key])
                # Handle complex objects - extract attributes
                elif isinstance(value, object) and not isinstance(value, (int, float, str, bool, type(None))):
                    processed_data[key] = {}
                    for attr_name in dir(value):
                        if not attr_name.startswith("_"):
                            try:
                                attr_value = getattr(value, attr_name)
                                if isinstance(attr_value, (int, float, str, bool, type(None))):
                                    if attr_value is None:
                                        processed_data[key][attr_name] = "None"
                                    # Mask password-related keys
                                    elif any(pw_key in attr_name.lower() for pw_key in masked_terms):
                                        processed_data[key][attr_name] = '*****'
                                    else:
                                        processed_data[key][attr_name] = attr_value
                            except:
                                continue
                # Handle primitive types
                else:
                    # Mask password-related keys
                    if any(pw_key in key.lower() for pw_key in masked_terms):
                        processed_data[key] = '*****'
                    elif isinstance(value, str) and "url" in key.lower():
                        processed_data[key] = pattern.sub(mask_pw, value)
                    else:
                        processed_data[key] = value

            if TRACEBACK_KEY_RESERVED_V2 not in processed_data:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                if exc_type and exc_value and exc_traceback:
                    processed_data[TRACEBACK_KEY_RESERVED_V2] = ''.join(traceback.format_exception(
                        exc_type, exc_value, exc_traceback))
                    processed_data[EXEC_TYPE_RESERVED_V2] = exc_type.__name__
                    processed_data[EXEC_VALUE_RESERVED_V2] = str(exc_value)

            # Add span ID from current span context if available
            current_span = LoggingContext.get_current_span()
            if current_span and current_span.span_id:
                processed_data[SPAN_ID_KEY_RESERVED_V2] = current_span.span_id
                processed_data[TRACE_ID_KEY_RESERVED_V2] = current_span.trace_id

            return processed_data
        except Exception as e:
            sdk_logger.error(
                f"Error in Log._prepare_log_data : {str(e)}: {traceback.format_exc()}")
            return {}

    @staticmethod
    def debug(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a debug message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            log_data[LEVEL_KEY_RESERVED_V2] = 'debug'
            Treebeard().add(log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.debug : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def info(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log an info message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            log_data[LEVEL_KEY_RESERVED_V2] = 'info'
            Treebeard().add(log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.info : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def warning(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a warning message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            log_data[LEVEL_KEY_RESERVED_V2] = 'warning'
            Treebeard().add(log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.warning : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def warn(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """alias for warning

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            Log.warning(message, data, **kwargs)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.warn : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def error(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log an error message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            log_data[LEVEL_KEY_RESERVED_V2] = 'error'
            Treebeard().add(log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.error : {str(e)}: {traceback.format_exc()}")

    @staticmethod
    def critical(message: str, data: Optional[Dict] = None, **kwargs) -> None:
        """Log a critical message.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments
        """
        try:
            log_data = Log._prepare_log_data(message, data, **kwargs)
            log_data[LEVEL_KEY_RESERVED_V2] = 'critical'
            Treebeard().add(log_data)
        except Exception as e:
            sdk_logger.error(
                f"Error in Log.critical : {str(e)}: {traceback.format_exc()}")

    @classmethod
    def _handle_exception(cls, exc_type: Type[BaseException], exc_value: BaseException, exc_traceback: Any) -> None:
        """Handle unhandled exceptions in the main thread.

        Args:
            exc_type: The type of the exception
            exc_value: The exception instance
            exc_traceback: The traceback object
        """
        try:

            # Log the exception
            Log.error(
                "Unhandled exception in main thread",
                error=exc_value,
            )

            # Clear the context after logging
            LoggingContext.clear()

            # Call the original exception handler
            if Treebeard._original_excepthook is not None:
                Treebeard._original_excepthook(
                    exc_type, exc_value, exc_traceback)

        except Exception as e:
            sdk_logger.error("Handled exception in SDK", error=e)

    @classmethod
    def _handle_threading_exception(cls, args: threading.ExceptHookArgs) -> None:
        """Handle unhandled exceptions in threads.

        Args:
            args: The exception hook arguments containing exception info
        """
        try:

            # Log the exception
            Log.error(
                "Unhandled exception in thread",
                thread_name=args.thread.name,
                thread_id=args.thread.ident,
                error=args.exc_value,

            )

            # Clear the context after logging
            LoggingContext.clear()

        # Call the original exception handler
            if Treebeard._original_threading_excepthook is not None:
                Treebeard._original_threading_excepthook(args)
        except Exception:
            sdk_logger.error("Handled exception in SDK")

    @classmethod
    def _handle_async_exception(cls, loop: asyncio.AbstractEventLoop, context: dict) -> None:
        """Handle unhandled exceptions in async contexts.

        Args:
            loop: The event loop where the exception occurred
            context: Dictionary containing exception information
        """
        try:
            exception = context.get('exception')

            if exception:
                # Log the exception
                Log.error(
                    "Unhandled exception in async context",
                    error=exception,

                    future=context.get('future'),
                    task=context.get('task'),
                    message=context.get('message'),

                )
            else:
                # Log the error message if no exception is present
                Log.error(
                    "Error in async context",
                    message=context.get('message'),
                    future=context.get('future'),
                    task=context.get('task'),
                )

            # Clear the context after logging
            LoggingContext.clear()

        # Call the original exception handler
            if Treebeard._original_loop_exception_handler is not None:
                Treebeard._original_loop_exception_handler(loop, context)
        except Exception:
            sdk_logger.error("Handled exception in SDK")

    @staticmethod
    def recurse_and_collect_dict(data: dict, collector: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """
        Process dictionary values while preserving structure. Handles masking of sensitive values,
        URL obfuscation, and proper handling of null/None values.

        Args:
            data: The dictionary to traverse.
            collector: The dictionary to populate.
            prefix: The current key prefix for nesting - only used for non-root collection.

        Returns:
            The updated collector dictionary.
        """
        # If we're at the root level (no prefix), we're creating a new nested dict
        if not prefix:
            for key, value in data.items():
                # For each key at the root level, process appropriately
                if isinstance(value, dict):
                    # Create a nested dictionary for dict values
                    collector[key] = {}
                    Log.recurse_and_collect_dict(value, collector[key], key)
                elif isinstance(value, list):
                    # Just store the count for lists
                    collector[f"{key}_count"] = len(value)
                elif isinstance(value, (str, int, float, bool, type(None))):
                    # Process primitive values
                    if value is None:
                        collector[key] = "None"
                    elif any(pw_key in key.lower() for pw_key in masked_terms):
                        collector[key] = '*****'
                    elif isinstance(value, str) and "url" in key.lower():
                        collector[key] = pattern.sub(mask_pw, value)
                    else:
                        collector[key] = value
                # Optionally handle other types here (e.g. sets, tuples)
        else:
            # We're inside a nested structure, continue adding to the passed collector
            for key, value in data.items():
                if isinstance(value, dict):
                    # Create a nested dictionary for this key
                    collector[key] = {}
                    Log.recurse_and_collect_dict(
                        value, collector[key], f"{prefix}_{key}")
                elif isinstance(value, list):
                    collector[f"{key}_count"] = len(value)
                elif isinstance(value, (str, int, float, bool, type(None))):
                    if value is None:
                        collector[key] = "None"
                    elif any(pw_key in key.lower() for pw_key in masked_terms) or any(pw_key in prefix.lower() for pw_key in masked_terms):
                        collector[key] = '*****'
                    elif isinstance(value, str) and "url" in key.lower():
                        collector[key] = pattern.sub(mask_pw, value)
                    else:
                        collector[key] = value
                # Optionally handle other types here

        return collector

    def extract_relevant_locals(locals_dict):
        result = {}
        for key, value in locals_dict.items():
            if key.startswith("__"):
                continue  # skip dunder
            if isinstance(value, (type(inspect), type(os))):  # skip modules
                continue
            if callable(value):
                continue  # skip functions and classes
            try:
                repr(value)
            except Exception:
                continue  # skip unrepr-able objects
            result[key] = value
        return result

    @staticmethod
    def enable_stdout_override() -> None:
        """
        Enable intercepting of stdout (print statements) and logging them as info logs.

        This will capture all print statements and log them as info logs
        while still allowing them to be printed to the original stdout.
        """
        StdoutOverride.enable()

    @staticmethod
    def disable_stdout_override() -> None:
        """
        Disable intercepting of stdout and restore original behavior.
        """
        StdoutOverride.disable()

    @staticmethod
    def is_stdout_override_enabled() -> bool:
        """
        Return whether stdout override is currently enabled.

        Returns:
            True if stdout override is enabled, False otherwise
        """
        return StdoutOverride.is_enabled()

    @staticmethod
    def enable_python_logger_forwarding(level: int = logging.DEBUG,
                                        logger_name: Optional[str] = None,
                                        ) -> None:
        """
        Enable forwarding of Python logger messages to Treebeard.

        Args:
            level: The minimum logging level to capture (default: DEBUG)
            logger_name: Specific logger name to attach to, or None for root logger
        """
        global _treebeard_handler

        if _treebeard_handler is None:
            _treebeard_handler = TreebeardHandler()
            _treebeard_handler.setLevel(level)

            # Get the target logger (root logger if no name specified)
            target_logger = logging.getLogger(logger_name)
            target_logger.addHandler(_treebeard_handler)

            # Ensure the logger level allows our handler to receive messages
            if target_logger.level > level:
                target_logger.setLevel(level)

            sdk_logger.debug(
                f"Treebeard Python logger forwarding enabled for logger: {logger_name or 'root'}")

    @staticmethod
    def disable_python_logger_forwarding(logger_name: Optional[str] = None) -> None:
        """
        Disable forwarding of Python logger messages to Treebeard.

        Args:
            logger_name: Specific logger name to detach from, or None for root logger
        """
        global _treebeard_handler

        if _treebeard_handler is not None:
            target_logger = logging.getLogger(logger_name)
            target_logger.removeHandler(_treebeard_handler)

            # Only clear the global handler if we're removing from root logger
            if logger_name is None:
                _treebeard_handler = None

            sdk_logger.debug(
                f"Treebeard Python logger forwarding disabled for logger: {logger_name or 'root'}")

    @staticmethod
    def is_python_logger_forwarding_enabled() -> bool:
        """
        Return whether Python logger forwarding is currently enabled.

        Returns:
            True if Python logger forwarding is enabled, False otherwise
        """
        return _treebeard_handler is not None


Treebeard.register_exception_handlers(Log._handle_exception,
                                      Log._handle_threading_exception, Log._handle_async_exception)


def mask_pw(match):
    return f"{match.group('db')}://{match.group('user')}:*****@{match.group('host')}:{match.group('port')}"


# print overrides
class StdoutOverride:
    """Class to override stdout and log printed messages through Treebeard."""

    _original_stdout: Optional[TextIO] = None
    _enabled: bool = False

    @classmethod
    def enable(cls) -> None:
        """Enable stdout override to capture prints as info logs."""
        if not cls._enabled:
            cls._original_stdout = sys.stdout
            sys.stdout = StdoutWriter(cls._original_stdout)
            cls._enabled = True
            sdk_logger.debug("Treebeard stdout override enabled")

    @classmethod
    def disable(cls) -> None:
        """Disable stdout override and restore original stdout."""
        if cls._enabled and cls._original_stdout is not None:
            sys.stdout = cls._original_stdout
            cls._original_stdout = None
            cls._enabled = False
            sdk_logger.debug("Treebeard stdout override disabled")

    @classmethod
    def is_enabled(cls) -> bool:
        """Return whether stdout override is enabled."""
        return cls._enabled


_guard = threading.local()


class StdoutWriter:
    """Custom stdout writer that logs messages through Treebeard."""

    def __init__(self, original_stdout: TextIO):
        """Initialize with the original stdout to forward output."""
        self.original_stdout = original_stdout

    def write(self, text: str) -> int:
        """
        Write text to both the original stdout and log as info.

        Args:
            text: The text to write

        Returns:
            Number of characters written
        """
        # don't take a frame from the SDK wrapper
        if getattr(_guard, "busy", False):          # already inside -> just pass through
            return self.original_stdout.write(text)

        _guard.busy = True
        try:
            # Only log non-empty, non-whitespace strings
            if text and not text.isspace():
                # Strip whitespace to clean up the log
                clean_text = text.rstrip()
                if clean_text:
                    # Find caller information outside the Treebeard module
                    # Log the printed text as info
                    Log.info(clean_text, {
                        SOURCE_KEY_RESERVED_V2: "print"
                    })
        except Exception as e:
            # Ensure we don't break stdout functionality if logging fails
            sdk_logger.error(f"Error in stdout override: {str(e)}")
        finally:
            _guard.busy = False

        # Always write to the original stdout
        return self.original_stdout.write(text)

    def flush(self) -> None:
        """Flush the original stdout."""
        self.original_stdout.flush()
