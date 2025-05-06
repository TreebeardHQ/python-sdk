"""
Core functionality for the treebeard library.
"""
import asyncio
import os
import sys
import time
import traceback
import signal
from typing import Optional, Dict, Any, List, TypedDict
import threading
import requests
import json
from queue import Queue, Empty
from termcolor import colored

from .batch import LogBatch
import logging
from .constants import COMPACT_SOURCE_KEY, COMPACT_TRACEBACK_KEY, COMPACT_TS_KEY, COMPACT_TRACE_ID_KEY, COMPACT_MESSAGE_KEY, COMPACT_LEVEL_KEY, SOURCE_KEY_RESERVED_V2, TS_KEY, LogEntry, COMPACT_FILE_KEY, COMPACT_LINE_KEY, COMPACT_TRACE_NAME_KEY, TRACE_ID_KEY_RESERVED_V2, MESSAGE_KEY_RESERVED_V2, LEVEL_KEY_RESERVED_V2, FILE_KEY_RESERVED_V2, LINE_KEY_RESERVED_V2, TRACEBACK_KEY_RESERVED_V2, TRACE_NAME_KEY_RESERVED_V2
from .internal_utils.fallback_logger import fallback_logger, sdk_logger
from .context import LoggingContext

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
_send_queue = Queue()

# Worker thread to process sending requests


class LogSenderWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()

    def run(self):
        while True:
            send_fn = _send_queue.get()
            if send_fn is None:  # shutdown signal
                break
            try:
                send_fn()
            except Exception as e:
                sdk_logger.error(
                    f"Unexpected error in log sender: {str(e)}")
            finally:
                _send_queue.task_done()

    def stop(self):
        self._stop_event.set()
        _send_queue.put(None)


_worker = LogSenderWorker()


# Handle shutdown signals


def _handle_shutdown(sig, frame):
    Treebeard().flush()
    sdk_logger.info("Shutdown signal received, flushing logs...")
    if _worker and _worker.is_alive():
        _worker.stop()
        _worker.join()


signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)

# Constants
DEFAULT_BATCH_SIZE = 100
DEFAULT_BATCH_AGE = 5.0
DEFAULT_API_URL = 'https://api.treebeardhq.com/logs/batch'


class Treebeard:
    _instance: Optional['Treebeard'] = None
    _initialized = False
    _api_key: Optional[str] = None
    _debug_mode: bool = False
    _batch: Optional[LogBatch] = None
    _endpoint: Optional[str] = None
    _env: Optional[str] = None
    _worker_started = False

    _original_excepthook: Optional[Any] = None
    _original_threading_excepthook: Optional[Any] = None
    _original_loop_exception_handler: Optional[Any] = None
    _project_name: Optional[str] = None

    _config_version: Optional[int] = None

    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, project_name: Optional[str] = None, api_key: Optional[str] = None, endpoint: Optional[str] = None,
                 batch_size: int = DEFAULT_BATCH_SIZE, batch_age: float = DEFAULT_BATCH_AGE, log_to_stdout: Optional[bool] = None, stdout_log_level: str = 'INFO',
                 capture_stdout: Optional[bool] = None):
        """
        Initialize the Treebeard class.

        Keyword Args:
            project_name: The project name for the Treebeard project. This is used to identify the project on the backend, so please be careful when changing it.
            api_key: The API key for the Treebeard project or set TREEBEARD_API_KEY in your environment.
            endpoint: (optional) The endpoint for the Treebeard project You may also set TREEBEARD_API_URL in your environment or it will use the default production endpoint
            batch_size: Configure the number of logs sent per batch
            batch_age: Configure how long to wait in between batches before sending logs regardless of batch size

            log_to_stdout: if true, Treebeard SDK will send everythign to standard out that we also send to out API
            stdout_log_level: the level to log to stdout. Defaults to INFO. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL, NOTSET

            capture_stdout: Whether to capture print statements as info logs. Defaults to False.
        """

        if Treebeard._initialized:
            return

        # accept some of these variables even if we've already initialized automatically
        if self._project_name is None and project_name is not None:
            # always accept the project name if it's provided
            self._project_name = project_name

        self._api_key = api_key or os.getenv('TREEBEARD_API_KEY')
        self._endpoint = endpoint or os.getenv(
            'TREEBEARD_API_URL', DEFAULT_API_URL)
        self._capture_stdout = capture_stdout if capture_stdout is not None else os.getenv(
            'TREEBEARD_CAPTURE_STDOUT', False)
        self._log_to_stdout = log_to_stdout if log_to_stdout is not None else os.getenv(
            'TREEBEARD_LOG_TO_STDOUT', False)

        self._stdout_log_level = stdout_log_level if stdout_log_level is not None else os.getenv(
            'TREEBEARD_STDOUT_LOG_LEVEL', 'INFO')

        self._env = os.getenv('ENV', "production")
        self._debug_mode = os.getenv(
            'TREEBEARD_DEBUG_MODE')

        # Enable stdout capture if requested
        if self._capture_stdout:
            # Import here to avoid circular imports
            from .log import Log
            Log.enable_stdout_override()

            if self._stdout_log_level:
                fallback_logger.setLevel(self._stdout_log_level)

        Treebeard._initialized = True

        # don't reset some of these if we've already initialized
        self._batch = LogBatch(max_size=batch_size, max_age=batch_age)
        self._using_fallback = not bool(self._api_key)

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

        if self._stdout_log_level:
            fallback_logger.setLevel(self._stdout_log_level)

        if self._capture_stdout:
            from .log import Log
            Log.enable_stdout_override()

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @property
    def debug_mode(self) -> bool:
        return self._debug_mode

    @classmethod
    def reset(cls) -> None:
        if cls._instance:
            cls._instance._api_key = None
            cls._instance._endpoint = None
            cls._instance._batch = None
            cls._instance._using_fallback = True
            cls._instance._log_to_stdout = False
            cls._instance._debug_mode = False
            cls._instance._capture_stdout = False
            cls._instance._env = None
            cls._initialized = False

    def add(self, log_entry: Dict[str, Any]) -> None:
        global found_api_key
        global has_warned
        global _worker

        if self._using_fallback:
            # let's check to see if we've lazy-loaded env vars
            key = os.getenv('TREEBEARD_API_KEY')
            if key:
                # reset env if we've found a key, just to make sure
                self._using_fallback = False
                self._env = os.getenv('ENV', self._env)
                self._endpoint = os.getenv(
                    'TREEBEARD_API_URL', self._endpoint)

                self._api_key = key
                self._log_to_stdout = os.getenv(
                    'TREEBEARD_LOG_TO_STDOUT', self._log_to_stdout)
                self._capture_stdout = os.getenv(
                    'TREEBEARD_CAPTURE_STDOUT', self._capture_stdout)

                self._stdout_log_level = os.getenv(
                    'TREEBEARD_STDOUT_LOG_LEVEL', self._stdout_log_level)

                self._initialized = True

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

        if not self._using_fallback and self._batch.add(self.format(log_entry)):

            if not Treebeard._worker_started:
                if not _worker.is_alive():
                    _worker = LogSenderWorker()
                    _worker.start()
                    sdk_logger.info(
                        "Treebeard log worker started post-fork.")
                Treebeard._worker_started = True
            self.flush()

        if self._using_fallback or self._env == "development" or self._log_to_stdout:
            self._log_to_fallback(log_entry)

    def format(self, log_entry: Dict[str, Any]) -> LogEntry:
        result: LogEntry = {}
        log_entry = log_entry.copy()
        result[COMPACT_TS_KEY] = log_entry.pop(
            TS_KEY, round(time.time() * 1000))
        result[COMPACT_TRACE_ID_KEY] = log_entry.pop(
            TRACE_ID_KEY_RESERVED_V2, '')
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

        if log_entry:
            result['props'] = {**log_entry}

        # not sure this is the best way to do this, but that's ok
        if result.get('props', {}).get(TRACE_NAME_KEY_RESERVED_V2):
            result['props'][COMPACT_TRACE_NAME_KEY] = result['props'].pop(
                TRACE_NAME_KEY_RESERVED_V2)
        return result

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
        file_path = log_entry.pop(FILE_KEY_RESERVED_V2, None)
        line_num = log_entry.pop(LINE_KEY_RESERVED_V2, None)
        ts = log_entry.pop('ts', None)

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
            formatted_message = colored(f"[{trace_id}] {message}", color)
            full_message = formatted_message + \
                ('\n' + metadata_str if metadata_str else '')

            fallback_logger.log(log_level, full_message)
        else:
            # Single line format for production (better for CloudWatch, etc.)
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
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
        if logs:
            self._send_logs(logs)

    def _send_logs(self, logs: List[Any]) -> None:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }
        data = json.dumps(
            {'logs': logs, 'project_name': self._project_name, "v": self._config_version})

        def send_request():
            max_retries = 3
            delay = 1  # seconds
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        self._endpoint, headers=headers, data=data)
                    if response.ok:
                        sdk_logger.debug(
                            f"Logs sent successfully. logs sent: {len(logs)}")

                        result = response.json()

                        # we get an updated config if the server has a later config version than we
                        # sent it
                        if isinstance(result, dict) and result.get('updated_config'):
                            self.update_project_config(
                                **result.get('updated_config'))

                        return result
                    else:
                        sdk_logger.warning(
                            f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
                except Exception as e:
                    sdk_logger.error("error while sending logs", exc_info=e)
                time.sleep(delay)
            sdk_logger.error("All attempts to send logs failed.")

        _send_queue.put(send_request)

    @classmethod
    def register(cls, excepthook: Optional[Any] = None, threading_excepthook: Optional[Any] = None, loop_exception_handler: Optional[Any] = None) -> None:
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
