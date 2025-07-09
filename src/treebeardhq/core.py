"""
Core functionality for the treebeard library.
"""
import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Union

from termcolor import colored

from treebeardhq.internal_utils.flush_timer import DEFAULT_FLUSH_INTERVAL, FlushTimerWorker

from .batch import LogBatch, ObjectBatch, SpanBatch
from .constants import (
    COMPACT_EXEC_TYPE_KEY,
    COMPACT_EXEC_VALUE_KEY,
    COMPACT_FILE_KEY,
    COMPACT_FUNCTION_KEY,
    COMPACT_LEVEL_KEY,
    COMPACT_LINE_KEY,
    COMPACT_MESSAGE_KEY,
    COMPACT_SOURCE_KEY,
    COMPACT_SPAN_ID_KEY,
    COMPACT_TRACE_ID_KEY,
    COMPACT_TRACE_NAME_KEY,
    COMPACT_TRACEBACK_KEY,
    COMPACT_TS_KEY,
    EXEC_TYPE_RESERVED_V2,
    EXEC_VALUE_RESERVED_V2,
    FILE_KEY_RESERVED_V2,
    FUNCTION_KEY_RESERVED_V2,
    LEVEL_KEY_RESERVED_V2,
    LINE_KEY_RESERVED_V2,
    MESSAGE_KEY_RESERVED_V2,
    SOURCE_KEY_RESERVED_V2,
    SPAN_ID_KEY_RESERVED_V2,
    TRACE_ID_KEY_RESERVED_V2,
    TRACE_NAME_KEY_RESERVED_V2,
    TRACEBACK_KEY_RESERVED_V2,
    TS_KEY,
    LogEntry,
)
from .context import LoggingContext
from .exporters import TreebeardExporter
from .internal_utils.fallback_logger import fallback_logger, sdk_logger
from .spans import SpanContext

LEVEL_COLORS = {
    'trace': 'white',
    'debug': 'dark_grey',
    'info': 'green',
    'warning': 'yellow',
    'error': 'red',
    'critical': 'red'
}

has_warned = False
found_api_key = False


# Handle shutdown signals


def _handle_shutdown(sig, frame):
    curr_time = round(time.time() * 1000)
    sdk_logger.info(
        "Shutdown signal received, flushing logs, objects, and spans...")
    treebeard_instance = Treebeard()
    treebeard_instance.flush()
    treebeard_instance.flush_objects()
    treebeard_instance.flush_spans()

    if Treebeard._instance and Treebeard._instance._flush_timer:
        Treebeard._instance._flush_timer.stop()
    if Treebeard._instance and Treebeard._instance._exporter:
        Treebeard._instance._exporter.stop_worker()

    sdk_logger.info(
        f"Shutdown complete, took {round(time.time() * 1000) - curr_time} ms")


signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)

# Constants
DEFAULT_BATCH_SIZE = 500
DEFAULT_BATCH_AGE = 30.0
DEFAULT_API_URL = 'https://api.treebeardhq.com/logs/batch'
DEFAULT_OBJECTS_API_URL = 'https://api.treebeardhq.com/objects/register'
DEFAULT_SPANS_API_URL = 'https://api.treebeardhq.com/spans/batch'


class Treebeard:
    _instance: Optional['Treebeard'] = None
    _initialized = False
    _api_key: Optional[str] = None
    _debug_mode: bool = False
    _batch: Optional[LogBatch] = None
    _object_batch: Optional[ObjectBatch] = None
    _span_batch: Optional[SpanBatch] = None
    _endpoint: Optional[str] = None
    _objects_endpoint: Optional[str] = None
    _spans_endpoint: Optional[str] = None
    _env: Optional[str] = None

    _original_excepthook: Optional[Any] = None
    _original_threading_excepthook: Optional[Any] = None
    _original_loop_exception_handler: Optional[Any] = None
    _project_name: Optional[str] = None
    _flush_interval: float = None
    _flush_timer: Optional[FlushTimerWorker] = None

    _config_version: Optional[int] = None
    _exporter: Optional[TreebeardExporter] = None

    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        project_name: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_age: float = DEFAULT_BATCH_AGE,
        log_to_stdout: Optional[bool] = None,
        stdout_log_level: str = 'INFO',
        capture_stdout: Optional[bool] = None,
        flush_interval: float = None,
        otel_format: Optional[bool] = None,
        capture_python_logger: Optional[bool] = None,
        python_logger_level: str = 'DEBUG',
        python_logger_name: Optional[str] = None,
    ):
        """
        Initialize the Treebeard class.

        Keyword Args:
            project_name: The project name for the Treebeard project. This is used to
                identify the project on the backend, so please be careful when changing it.
            api_key: The API key for the Treebeard project or set TREEBEARD_API_KEY
                in your environment.
            endpoint: (optional) The endpoint for the Treebeard project You may also set
                TREEBEARD_API_URL in your environment or it will use the default
                production endpoint
            batch_size: Configure the number of logs sent per batch
            batch_age: Configure how long to wait in between batches before sending logs
                regardless of batch size

            log_to_stdout: if true, Treebeard SDK will send everything to standard out
                that we also send to out API
            stdout_log_level: the level to log to stdout. Defaults to INFO.
                Options: DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL, NOTSET

            capture_stdout: Whether to capture print statements as info logs.
                Defaults to False.
            otel_format: Whether to format logs according to OpenTelemetry specification.
                Defaults to False.
            capture_python_logger: Whether to capture standard Python logger messages.
                Defaults to False.
            python_logger_level: The minimum logging level to capture from Python logger.
                Defaults to 'DEBUG'. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL.
            python_logger_name: Specific logger name to capture from, or None for root logger.
                Defaults to None (captures from root logger).
        """

        # accept some of these variables even if we've already initialized automatically
        if project_name is not None:
            # always accept the project name if it's provided
            self._project_name = project_name

        if Treebeard._initialized:
            return

        self._api_key = api_key if api_key else os.getenv(
            'TREEBEARD_API_KEY')

        if self._api_key and not isinstance(self._api_key, str):
            raise ValueError("API key must be a string")

        self._api_key = self._api_key.strip() if self._api_key else None

        self._endpoint = endpoint or os.getenv(
            'TREEBEARD_API_URL', DEFAULT_API_URL)
        self._objects_endpoint = (
            self._endpoint.replace('/logs/batch', '/objects/register')
            if self._endpoint else DEFAULT_OBJECTS_API_URL
        )
        self._spans_endpoint = (
            self._endpoint.replace('/logs/batch', '/spans/batch')
            if self._endpoint else DEFAULT_SPANS_API_URL
        )
        self._capture_stdout = capture_stdout if capture_stdout is not None else os.getenv(
            'TREEBEARD_CAPTURE_STDOUT', False)
        self._log_to_stdout = log_to_stdout if log_to_stdout is not None else os.getenv(
            'TREEBEARD_LOG_TO_STDOUT', False)

        self._stdout_log_level = stdout_log_level if stdout_log_level is not None else os.getenv(
            'TREEBEARD_STDOUT_LOG_LEVEL', 'INFO')

        self._capture_python_logger = (
            capture_python_logger if capture_python_logger is not None
            else os.getenv('TREEBEARD_CAPTURE_PYTHON_LOGGER', False)
        )
        self._python_logger_level = (
            python_logger_level if python_logger_level is not None
            else os.getenv('TREEBEARD_PYTHON_LOGGER_LEVEL', 'DEBUG')
        )
        self._python_logger_name = (
            python_logger_name if python_logger_name is not None
            else os.getenv('TREEBEARD_PYTHON_LOGGER_NAME', None)
        )

        self._env = os.getenv('ENV', "production")
        self._debug_mode = os.getenv(
            'TREEBEARD_DEBUG_MODE')

        self._flush_interval = flush_interval if flush_interval is not None else os.getenv(
            'TREEBEARD_FLUSH_INTERVAL', DEFAULT_FLUSH_INTERVAL)

        self._otel_format = otel_format if otel_format is not None else os.getenv(
            'TREEBEARD_OTEL_FORMAT', False)

        # Enable stdout capture if requested
        if self._capture_stdout:
            # Import here to avoid circular imports
            from .log import Log
            Log.enable_stdout_override()

            if self._stdout_log_level:
                fallback_logger.setLevel(self._stdout_log_level)

        # Enable Python logger capture if requested
        if self._capture_python_logger:
            # Import here to avoid circular imports
            from .log import Log
            # Map string level to logging constant
            level_map = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL
            }
            log_level = level_map.get(
                self._python_logger_level.upper(), logging.DEBUG)
            Log.enable_python_logger_forwarding(
                level=log_level, logger_name=self._python_logger_name)

        Treebeard._initialized = True

        # don't reset some of these if we've already initialized
        self._batch = LogBatch(max_size=batch_size, max_age=batch_age)
        self._object_batch = ObjectBatch(
            max_size=batch_size, max_age=batch_age)
        self._span_batch = SpanBatch(max_size=batch_size, max_age=batch_age)
        self._using_fallback = not bool(self._api_key)

        if self._flush_timer is None:
            self._flush_timer = FlushTimerWorker(
                treebeard_ref=self, interval=self._flush_interval)
            self._flush_timer.start()

        # Initialize exporter if we have an API key
        if self._api_key and not self._using_fallback:
            self._exporter = TreebeardExporter(
                api_key=self._api_key,
                endpoint=self._endpoint,
                objects_endpoint=self._objects_endpoint,
                spans_endpoint=self._spans_endpoint,
                project_name=self._project_name
            )

        if self._api_key:
            sdk_logger.info(
                f"Treebeard initialized with config: {self.__dict__}")
        else:
            sdk_logger.warning(
                "No API key provided - using fallback logger.")

    @classmethod
    def init(cls, **kwargs: Any) -> None:
        """
        Initialize the Treebeard class.

        @see Treebeard.__init__
        """
        cls(**kwargs)  # Triggers __new__ and __init__

    def update_project_config(self, **kwargs: Any) -> None:
        """
        Update the project config.
        """

        self._config_version = kwargs.get(
            'config_version', self._config_version)

        self._log_to_stdout = bool(kwargs.get(
            'log_to_stdout', self._log_to_stdout))
        self._stdout_log_level = kwargs.get(
            'stdout_log_level', self._stdout_log_level)
        self._capture_stdout = bool(kwargs.get(
            'capture_stdout', self._capture_stdout))
        self._otel_format = bool(kwargs.get(
            'otel_format', self._otel_format))
        self._capture_python_logger = bool(kwargs.get(
            'capture_python_logger', self._capture_python_logger))
        self._python_logger_level = kwargs.get(
            'python_logger_level', self._python_logger_level)
        self._python_logger_name = kwargs.get(
            'python_logger_name', self._python_logger_name)

        if self._stdout_log_level:
            fallback_logger.setLevel(self._stdout_log_level)

        if self._capture_stdout:
            from .log import Log
            Log.enable_stdout_override()

        if self._capture_python_logger:
            from .log import Log
            # Map string level to logging constant
            level_map = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL
            }
            log_level = level_map.get(
                self._python_logger_level.upper(), logging.DEBUG)
            Log.enable_python_logger_forwarding(
                level=log_level, logger_name=self._python_logger_name)

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @property
    def debug_mode(self) -> bool:
        return self._debug_mode

    @classmethod
    def reset(cls) -> None:
        global has_warned
        global found_api_key

        has_warned = False
        found_api_key = False
        if cls._instance:
            cls._instance._api_key = None
            cls._instance._endpoint = None
            cls._instance._objects_endpoint = None
            cls._instance._batch = None
            cls._instance._object_batch = None
            cls._instance._span_batch = None
            cls._instance._using_fallback = True
            cls._instance._log_to_stdout = False
            cls._instance._debug_mode = False
            cls._instance._capture_stdout = False
            cls._instance._env = None
            cls._instance._project_name = None
            cls._instance._otel_format = False
            cls._instance._capture_python_logger = False
            cls._instance._python_logger_level = 'DEBUG'
            cls._instance._python_logger_name = None
            cls._initialized = False

    def add(self, log_entry: Dict[str, Any]) -> None:
        global found_api_key
        global has_warned

        if self._using_fallback:
            # let's check to see if we've lazy-loaded env vars
            key = os.getenv('TREEBEARD_API_KEY')
            if key and key.strip() != "":
                # reset env if we've found a key, just to make sure
                self._using_fallback = False
                self._env = os.getenv('ENV', self._env)
                self._endpoint = os.getenv(
                    'TREEBEARD_API_URL', self._endpoint)

                self._api_key = key.strip()
                self._log_to_stdout = os.getenv(
                    'TREEBEARD_LOG_TO_STDOUT', self._log_to_stdout)
                self._capture_stdout = os.getenv(
                    'TREEBEARD_CAPTURE_STDOUT', self._capture_stdout)

                self._stdout_log_level = os.getenv(
                    'TREEBEARD_STDOUT_LOG_LEVEL', self._stdout_log_level)

                self._initialized = True

                # Initialize exporter after lazy loading API key
                if not self._exporter:
                    self._exporter = TreebeardExporter(
                        api_key=self._api_key,
                        endpoint=self._endpoint,
                        objects_endpoint=self._objects_endpoint,
                        spans_endpoint=self._spans_endpoint,
                        project_name=self._project_name
                    )

                if has_warned:
                    sdk_logger.info(
                        f"Treebeard lazy-loaded API key: {key} and endpoint: {self._endpoint}.")

        if not self._initialized:
            if not has_warned:
                sdk_logger.warning(
                    "Treebeard is not initialized - logs will be output to standard Python logger")
                has_warned = True
            self._log_to_fallback(log_entry)
            return

        if not self._using_fallback and self._batch.add(self.format_log(log_entry)):

            self.flush()

        if self._using_fallback or self._env == "development" or self._log_to_stdout:
            self._log_to_fallback(log_entry)

    def format_log(self, log_entry: Dict[str, Any]) -> LogEntry:
        """Format log entry based on configuration."""
        if self._otel_format:
            return self.format_otel(log_entry)
        else:
            return self.format(log_entry)

    def format(self, log_entry: Dict[str, Any]) -> LogEntry:
        result: LogEntry = {}
        log_entry = log_entry.copy()
        result[COMPACT_TS_KEY] = log_entry.pop(
            TS_KEY, round(time.time() * 1000))
        result[COMPACT_TRACE_ID_KEY] = log_entry.pop(
            TRACE_ID_KEY_RESERVED_V2, '')
        result[COMPACT_SPAN_ID_KEY] = log_entry.pop(
            SPAN_ID_KEY_RESERVED_V2, '')
        result[COMPACT_MESSAGE_KEY] = log_entry.pop(
            MESSAGE_KEY_RESERVED_V2, '')
        result[COMPACT_LEVEL_KEY] = log_entry.pop(
            LEVEL_KEY_RESERVED_V2, 'debug')
        result[COMPACT_FILE_KEY] = log_entry.pop(FILE_KEY_RESERVED_V2, '')
        result[COMPACT_LINE_KEY] = log_entry.pop(LINE_KEY_RESERVED_V2, '')
        result[COMPACT_TRACEBACK_KEY] = log_entry.pop(
            TRACEBACK_KEY_RESERVED_V2, '')
        result[COMPACT_SOURCE_KEY] = log_entry.pop(
            SOURCE_KEY_RESERVED_V2, 'treebeard')
        result[COMPACT_FUNCTION_KEY] = log_entry.pop(
            FUNCTION_KEY_RESERVED_V2, '')
        result[COMPACT_EXEC_TYPE_KEY] = log_entry.pop(
            EXEC_TYPE_RESERVED_V2, '')
        result[COMPACT_EXEC_VALUE_KEY] = log_entry.pop(
            EXEC_VALUE_RESERVED_V2, '')

        if log_entry:
            result['props'] = {**log_entry}

        # not sure this is the best way to do this, but that's ok
        if result.get('props', {}).get(TRACE_NAME_KEY_RESERVED_V2):
            result['props'][COMPACT_TRACE_NAME_KEY] = result['props'].pop(
                TRACE_NAME_KEY_RESERVED_V2)
        return result

    def format_otel(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Format log entry according to OpenTelemetry specification."""
        log_entry = log_entry.copy()

        # Create OpenTelemetry-compliant log record
        otel_log = {}

        # Timestamp - convert to nanoseconds if needed
        timestamp = log_entry.pop(TS_KEY, round(time.time() * 1000))
        if isinstance(timestamp, (int, float)):
            # Convert milliseconds to nanoseconds for OTel
            otel_log["Timestamp"] = str(int(timestamp * 1_000_000))

        # Trace context
        trace_id = log_entry.pop(TRACE_ID_KEY_RESERVED_V2, '')
        if trace_id:
            otel_log["TraceId"] = trace_id

        # Span context
        span_id = log_entry.pop(SPAN_ID_KEY_RESERVED_V2, '')
        if span_id:
            otel_log["SpanId"] = span_id

        # Severity
        level = log_entry.pop(LEVEL_KEY_RESERVED_V2, 'info')
        severity_map = {
            'trace': {'text': 'TRACE', 'number': 1},
            'debug': {'text': 'DEBUG', 'number': 5},
            'info': {'text': 'INFO', 'number': 9},
            'warning': {'text': 'WARN', 'number': 13},
            'error': {'text': 'ERROR', 'number': 17},
            'critical': {'text': 'FATAL', 'number': 21}
        }
        severity = severity_map.get(level, severity_map['info'])
        otel_log["SeverityText"] = severity['text']
        otel_log["SeverityNumber"] = severity['number']

        # Body (message)
        message = log_entry.pop(MESSAGE_KEY_RESERVED_V2, '')
        otel_log["Body"] = message

        # Resource attributes
        resource = {}
        if self._project_name:
            resource["service.name"] = self._project_name

        # Add source as resource attribute
        source = log_entry.pop(SOURCE_KEY_RESERVED_V2, 'treebeard')
        resource["source"] = source

        if resource:
            otel_log["Resource"] = resource

        # InstrumentationScope
        otel_log["InstrumentationScope"] = {
            "Name": "treebeard-python-sdk",
            "Version": "2.0"
        }

        # Attributes - collect remaining fields
        attributes = {}

        # File and line information
        file_path = log_entry.pop(FILE_KEY_RESERVED_V2, '')
        if file_path:
            attributes["code.filepath"] = file_path

        line_num = log_entry.pop(LINE_KEY_RESERVED_V2, '')
        if line_num:
            attributes["code.lineno"] = line_num

        function_name = log_entry.pop(FUNCTION_KEY_RESERVED_V2, '')
        if function_name:
            attributes["code.function"] = function_name

        # Exception information
        exec_type = log_entry.pop(EXEC_TYPE_RESERVED_V2, '')
        exec_value = log_entry.pop(EXEC_VALUE_RESERVED_V2, '')
        traceback_str = log_entry.pop(TRACEBACK_KEY_RESERVED_V2, '')

        if exec_type:
            attributes["exception.type"] = exec_type
        if exec_value:
            attributes["exception.message"] = exec_value
        if traceback_str:
            attributes["exception.stacktrace"] = traceback_str

        # Trace name
        trace_name = log_entry.pop(TRACE_NAME_KEY_RESERVED_V2, '')
        if trace_name:
            attributes["trace.name"] = trace_name

        # Add any remaining fields as attributes
        for key, value in log_entry.items():
            if value is not None:
                attributes[key] = value

        if attributes:
            otel_log["Attributes"] = attributes

        return otel_log

    def _log_to_fallback(self, log_entry: Dict[str, Any]) -> None:

        if self._log_to_stdout and log_entry.get(SOURCE_KEY_RESERVED_V2) == "print":
            # print statements are forwarded to stdout already, so don't print them again
            # alternatively, we should probably not forward them to stdout, but not sure
            # what the customer preference is
            return

        level = log_entry.pop(LEVEL_KEY_RESERVED_V2, 'info')
        message = log_entry.pop(MESSAGE_KEY_RESERVED_V2, '')
        error = log_entry.pop('error', None)
        trace_id = log_entry.pop(TRACE_ID_KEY_RESERVED_V2, None)
        span_id = log_entry.pop(SPAN_ID_KEY_RESERVED_V2, None)
        file_path = log_entry.pop(FILE_KEY_RESERVED_V2, None)
        line_num = log_entry.pop(LINE_KEY_RESERVED_V2, None)
        log_entry.pop('ts', None)

        metadata = {k: v for k, v in log_entry.items() if k != 'level'}

        level_map = {
            'trace': logging.DEBUG,
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
        }
        log_level = level_map.get(level, logging.INFO)

        # Use pretty format for development environment
        if self._env == "development" or self._debug_mode:
            metadata_str = ''
            if metadata:
                formatted_metadata = self.dict_to_yaml_like(metadata)
                metadata_str = f"{colored(formatted_metadata, 'dark_grey')}"

            color = LEVEL_COLORS.get(level, 'white')
            if span_id:
                formatted_message = colored(
                    f"[{trace_id}:{span_id}] {message}", color)
            else:
                formatted_message = colored(
                    f"[{trace_id}] {message}", color)
            full_message = formatted_message + \
                ('\n' + metadata_str if metadata_str else '')

            fallback_logger.log(log_level, full_message)
        else:
            # Single line format for production (better for CloudWatch, etc.)
            time.strftime('%Y-%m-%d %H:%M:%S')
            if span_id:
                log_info = f"[{trace_id}:{span_id}] {message}"
            else:
                log_info = f"[{trace_id}] {message}"

            if file_path and line_num:
                log_info += f" ({os.path.basename(file_path)}:{line_num})"

            if metadata:
                # Convert metadata to JSON string to ensure it's a single line
                json_metadata = json.dumps(metadata)
                log_info += f" -- attributes: {json_metadata}"

            fallback_logger.log(log_level, log_info)

        if error and isinstance(error, Exception) and error.__traceback__:
            trace = ''.join(traceback.format_exception(
                type(error), error, error.__traceback__))
            fallback_logger.log(log_level, trace)

        else:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if exc_traceback and exc_type and exc_value:
                trace = ''.join(traceback.format_exception(
                    exc_type, exc_value, exc_traceback))
                fallback_logger.log(log_level, trace)

    def dict_to_yaml_like(self, data: dict) -> str:
        lines = []
        for key, value in data.items():
            if isinstance(value, str):
                line = f"{key}: \"{value}\""
            elif value is None:
                line = f"{key}: null"
            elif isinstance(value, bool):
                line = f"{key}: {'true' if value else 'false'}"
            else:
                line = f"{key}: {value}"
            lines.append(line)
        return '\n'.join(lines)

    def flush(self) -> None:
        if not self._initialized:
            raise RuntimeError(
                "Treebeard must be initialized before flushing logs")

        logs = self._batch.get_logs()
        count = len(logs)
        if logs and self._exporter:
            self._exporter.send_logs_async(
                logs, self._config_version, self.update_project_config)

        return count

    def register_object(self, obj: Any = None, **kwargs: Any) -> None:
        """Register objects for tracking in Treebeard.

        Args:
            obj: Object to register (optional, can be dict or object with attributes)
            **kwargs: Object data to register as keyword arguments. Should include an 'id' field.
        """
        if not self._initialized:
            sdk_logger.warning(
                "Treebeard is not initialized - object registration will be skipped")
            return

        # Handle single object registration
        if obj is not None:

            data_to_register = obj
            formatted_obj = self._format_object(data_to_register)
            if formatted_obj is not None:
                self._attach_to_context(formatted_obj)
                if not self._using_fallback and self._object_batch.add(formatted_obj):
                    self.flush_objects()
            return

        # Handle kwargs registration - register each key-value pair
        if not kwargs:
            sdk_logger.warning("No object or kwargs provided for registration")
            return

        for key, value in kwargs.items():
            if not isinstance(value, dict):
                # Add the key as an attribute to help with naming
                value._kwarg_key = key

            formatted_obj = self._format_object(value)
            if formatted_obj is not None:
                self._attach_to_context(formatted_obj)
                if not self._using_fallback and self._object_batch.add(formatted_obj):
                    self.flush_objects()

    def _format_object(self, obj_data: Union[Dict[str, Any], Any]) -> Optional[Dict[str, Any]]:
        """Format and validate an object for registration.

        Args:
            obj_data: Raw object data (dict or object with attributes)

        Returns:
            Formatted object or None if validation fails
        """
        # Convert object to dict if needed
        if not isinstance(obj_data, dict):
            # Get class name if it's a class instance
            class_name = obj_data.__class__.__name__ if hasattr(
                obj_data, '__class__') else None

            # Convert object attributes to dict
            try:
                if hasattr(obj_data, '__dict__'):
                    obj_dict = obj_data.__dict__.copy()
                else:
                    # Try to convert using vars()
                    obj_dict = vars(obj_data)
            except TypeError:
                sdk_logger.warning(
                    "Cannot convert object to dictionary for registration")
                return None
        else:
            obj_dict = obj_data.copy()
            class_name = None

        # Check for ID field and warn if missing
        if 'id' not in obj_dict:
            sdk_logger.warning(
                "Object registered without 'id' field. This may cause issues with object tracking.")
            return None

        name = None
        if class_name:
            name = class_name.lower()
        if not name and hasattr(obj_data, '_kwarg_key'):
            name = obj_data._kwarg_key.lower()

        obj_id = obj_dict.get('id')

        # Validate and filter fields
        fields = {}
        for key, value in obj_dict.items():
            if key in ['name', 'id']:
                continue

            field_value = self._format_field(key, value)
            if field_value:
                fields[key] = field_value

        return {
            'name': name,
            'id': obj_id,
            'fields': fields
        }

    def _format_field(self, key: str, value: Any) -> bool:
        """Validate if a field should be included in object registration.

        Args:
            key: Field name
            value: Field value

        Returns:
            True if field is valid for registration
        """
        # Check for numbers
        if isinstance(value, (int, float)):
            return value

        # Check for booleans
        if isinstance(value, bool):
            return value

        # Check for dates
        if isinstance(value, datetime):
            return value.isoformat()

        # Check for searchable strings (under 1024 chars)
        if isinstance(value, str):
            if len(value) <= 1024:
                # Simple heuristic: if it looks like metadata (short, no newlines)
                # rather than body text
                valid = '\n' not in value and '\r' not in value
                if valid:
                    return value

        return None

    def _attach_to_context(self, formatted_obj: Dict[str, Any]) -> None:
        """Attach the registered object to the current trace context.

        Args:
            formatted_obj: The formatted object with name, id, and fields
        """
        object_name = formatted_obj.get('name', '')
        object_id = formatted_obj.get('id', '')

        if object_name and object_id:
            # Create context key as {name}_id
            context_key = f"{object_name}_id"

            # Set the context value to the object's ID
            LoggingContext.set(context_key, object_id)

            sdk_logger.debug(
                f"Attached object to context: {context_key} = {object_id}")

    def flush_objects(self) -> int:
        """Flush all pending object registrations.

        Returns:
            Number of objects flushed
        """
        if not self._initialized:
            raise RuntimeError(
                "Treebeard must be initialized before flushing objects")

        objects = self._object_batch.get_objects()
        count = len(objects)
        if objects and self._exporter:
            self._exporter.send_objects_async(
                objects, self._config_version, self.update_project_config
            )

        return count

    def add_span(self, span) -> None:
        """Add a span to the span batch.

        Args:
            span: The span to add to the batch
        """
        if not self._initialized:
            return

        if not self._using_fallback and self._span_batch:
            if self._span_batch.add(span):
                if not self._exporter:
                    self._exporter = TreebeardExporter(
                        api_key=self._api_key,
                        endpoint=self._endpoint,
                        objects_endpoint=self._objects_endpoint,
                        spans_endpoint=self._spans_endpoint,
                        project_name=self._project_name
                    )
                self._exporter.start_worker()
                self.flush_spans()

    def flush_spans(self) -> int:
        """Flush all pending spans.

        Returns:
            Number of spans flushed
        """
        if not self._initialized:
            raise RuntimeError(
                "Treebeard must be initialized before flushing spans")

        spans = self._span_batch.get_spans()
        count = len(spans)
        if spans and self._exporter:
            self._exporter.send_spans_async(
                spans, self._config_version, self.update_project_config
            )

        return count

    @staticmethod
    def parse_traceparent(traceparent: str) -> Optional[Dict[str, str]]:
        """Parse W3C traceparent header into its components.

        The traceparent header format is: version-trace_id-parent_id-flags

        Args:
            traceparent: The traceparent header value

        Returns:
            Dictionary with 'trace_id', 'parent_id', and 'flags', or None if invalid
        """
        if not traceparent or not isinstance(traceparent, str):
            return None

        parts = traceparent.strip().split('-')
        if len(parts) != 4:
            return None

        version, trace_id, parent_id, flags = parts

        # Validate format
        if len(version) != 2 or len(trace_id) != 32 or len(parent_id) != 16 or len(flags) != 2:
            return None

        # Validate hex format
        try:
            int(version, 16)
            int(trace_id, 16)
            int(parent_id, 16)
            int(flags, 16)
        except ValueError:
            return None

        return {
            'version': version,
            'trace_id': trace_id,
            'parent_id': parent_id,
            'flags': flags
        }

    @staticmethod
    def establish_trace_context(
        trace_id: str,
        parent_span_id: str,
        clear_existing: bool = True
    ) -> SpanContext:
        """Establish a trace context from incoming distributed tracing headers.

        This method sets up the logging context with the proper trace_id and
        creates a span context that can be used to start child spans.

        Args:
            trace_id: The trace ID from the parent request
            parent_span_id: The span ID of the parent span
            clear_existing: Whether to clear existing context first

        Returns:
            SpanContext that can be used to start child spans
        """
        if clear_existing:
            LoggingContext.clear()
            LoggingContext.clear_span_stack()

        # Create a span context representing the remote parent
        span_context = SpanContext(
            trace_id=trace_id,
            span_id=parent_span_id,
            parent_span_id=None  # This is the remote parent
        )

        return span_context

    @classmethod
    def register(cls, obj: Any = None, **kwargs: Any) -> None:
        """Register objects for tracking in Treebeard (class method).

        Args:
            obj: Object to register (optional, can be dict or object with attributes)
            **kwargs: Object data to register as keyword arguments. Should include an 'id' field.
        """
        instance = cls()
        instance.register_object(obj, **kwargs)

    @classmethod
    def register_exception_handlers(
        cls,
        excepthook: Optional[Any] = None,
        threading_excepthook: Optional[Any] = None,
        loop_exception_handler: Optional[Any] = None,
    ) -> None:
        """Register the global exception handler for all contexts."""
        # Register for main thread exceptions
        if cls._original_excepthook is None:
            cls._original_excepthook = sys.excepthook
            sys.excepthook = excepthook

        # Register for threading exceptions
        if cls._original_threading_excepthook is None:
            cls._original_threading_excepthook = threading.excepthook
            threading.excepthook = threading_excepthook

        # Register for asyncio exceptions
        if cls._original_loop_exception_handler is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop:
                cls._original_loop_exception_handler = loop.get_exception_handler()
                loop.set_exception_handler(loop_exception_handler)

    @classmethod
    def unregister(cls) -> None:
        """Unregister the global exception handler from all contexts."""
        if cls._original_excepthook is not None:
            sys.excepthook = cls._original_excepthook
            cls._original_excepthook = None

        if cls._original_threading_excepthook is not None:
            threading.excepthook = cls._original_threading_excepthook
            cls._original_threading_excepthook = None

        if cls._original_loop_exception_handler is not None:
            try:
                loop = asyncio.get_event_loop()
                loop.set_exception_handler(
                    cls._original_loop_exception_handler)
                cls._original_loop_exception_handler = None
            except RuntimeError:
                # No event loop in this thread, that's fine
                pass
