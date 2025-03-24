"""
Core functionality for the treebeard library.
"""
from typing import Optional, Dict, Any, List
import threading
import requests
import json
import logging
import pprint
from termcolor import colored
from .batch import LogBatch
from .utils import ThreadingMode, detect_threading_mode

# Configure the fallback logger
fallback_logger = logging.getLogger('treebeard')
if not fallback_logger.handlers:
    handler = logging.StreamHandler()
    fallback_logger.addHandler(handler)
    fallback_logger.setLevel(logging.DEBUG)

# Map log levels to colors
LEVEL_COLORS = {
    'trace': 'white',
    'debug': 'dark_grey',
    'info': 'green',
    'warning': 'yellow',
    'error': 'red',
    'critical': 'red'
}


class Treebeard:
    """Main class for handling log forwarding."""
    _instance: Optional['Treebeard'] = None
    _initialized = False

    def __new__(cls, endpoint: Optional[str] = None, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize instance attributes here
            cls._instance._api_key = None
            cls._instance._debug_mode = False
            cls._instance._batch = None
            cls._instance.endpoint = None
            cls._instance._threading_mode = None
        return cls._instance

    def __init__(self, endpoint: Optional[str] = None, batch_size: int = 100, batch_age: float = 5.0):
        """Initialize Treebeard.

        Args:
            endpoint: The endpoint URL to send logs to
            batch_size: Maximum number of logs to batch before sending
            batch_age: Maximum age in seconds before sending a batch
        """
        if not self._initialized and endpoint is not None:
            self.endpoint = endpoint
            self._batch = LogBatch(max_size=batch_size, max_age=batch_age)
            self._using_fallback = False

    @classmethod
    def init(cls, api_key: Optional[str] = None, **config: Any) -> None:
        """Initialize Treebeard with optional API key and configuration.

        Args:
            api_key: Optional authentication key for the logging endpoint
            **config: Optional configuration parameters
        """
        if cls._initialized:
            raise RuntimeError("Treebeard is already initialized")

        instance = cls()

        # Check api_key type first if provided
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError("API key must be a string")

        # Now check if we have a valid API key
        if api_key is None or not api_key.strip():
            fallback_logger.warning(
                "No API key provided - logs will be output to standard Python logger"
            )
            instance._using_fallback = True
        else:
            instance._api_key = api_key.strip()
            instance._using_fallback = False
            endpoint = config.get('endpoint')
            if not endpoint:
                raise ValueError(
                    "endpoint must be provided when using API key")

            instance.endpoint = endpoint
            instance._batch = LogBatch(
                max_size=config.get('batch_size', 100),
                max_age=config.get('batch_age', 5.0)
            )

        # Set threading mode if using API
        if not instance._using_fallback:
            threading_mode = config.get('threading_mode')
            if threading_mode:
                instance._threading_mode = ThreadingMode(threading_mode)
            else:
                instance._threading_mode, _ = detect_threading_mode()

        instance._debug_mode = bool(config.get('debug_mode', False))
        cls._initialized = True

    @property
    def api_key(self) -> Optional[str]:
        """Get the API key."""
        return self._api_key

    @property
    def debug_mode(self) -> bool:
        """Get the debug mode status."""
        return self._debug_mode

    @classmethod
    def reset(cls) -> None:
        """Reset the Treebeard singleton (mainly for testing)."""
        if cls._instance is not None:
            cls._instance._api_key = None
            cls._instance._debug_mode = False
            cls._instance.endpoint = None
            cls._instance._batch = None
            cls._initialized = False

    def add(self, log_entry: Any) -> None:
        """Add a log entry to the batch or fallback logger.

        Args:
            log_entry: The log entry to add (can be any serializable type)
        """
        if not self._initialized:
            raise RuntimeError(
                "Treebeard must be initialized before adding logs")

        if self._using_fallback:
            self._log_to_fallback(log_entry)
        else:
            if self._batch.add(log_entry):
                self.flush()

    def _log_to_fallback(self, log_entry: Dict[str, Any]) -> None:
        """Log to the fallback logger with pretty formatting and colors.

        Args:
            log_entry: The log entry to format and output
        """
        level = log_entry.get('level', 'info')
        message = log_entry.pop('message', '')

        # Create a copy of the log entry without level and message
        metadata = {k: v for k, v in log_entry.items() if k != 'level'}

        # Format the metadata if present
        metadata_str = ''
        if metadata:
            formatted_metadata = pprint.pformat(metadata, indent=2)
            metadata_str = f"{colored(formatted_metadata, 'dark_grey')}"

        # Color the output based on level
        color = LEVEL_COLORS.get(level, 'white')
        formatted_message = colored(message, color)

        # Map to standard logging levels
        level_map = {
            'trace': logging.DEBUG,
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
        }
        log_level = level_map.get(level, logging.INFO)

        fallback_logger.log(log_level, formatted_message)
        fallback_logger.log(log_level, metadata_str)

    def flush(self) -> None:
        """Force flush all pending logs to the server."""
        if not self._initialized:
            raise RuntimeError(
                "Treebeard must be initialized before flushing logs")

        logs = self._batch.get_logs()
        if logs:
            self._send_logs(logs)

    def _send_logs(self, logs: List[Any]) -> None:
        """Send logs to the server asynchronously using the configured threading mode.

        Args:
            logs: List of log entries to send
        """
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }

        data = json.dumps({'logs': logs})

        def send_request():
            try:
                response = requests.post(
                    self.endpoint, headers=headers, data=data)
                if self._debug_mode:
                    print(f"Log batch sent. Status: {response.status_code}")
                if not response.ok:
                    print(
                        f"Failed to send logs. Status: {response.status_code}, Response: {response.text}")
            except Exception as e:
                if self._debug_mode:
                    print(f"Error sending logs: {str(e)}")

        if self._threading_mode == ThreadingMode.THREAD:
            thread = threading.Thread(target=send_request)
            thread.daemon = True
            thread.start()

        elif self._threading_mode == ThreadingMode.EVENTLET:
            import eventlet
            eventlet.spawn(send_request)

        elif self._threading_mode == ThreadingMode.GEVENT:
            import gevent
            gevent.spawn(send_request)
