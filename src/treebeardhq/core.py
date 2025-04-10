"""
Core functionality for the treebeard library.
"""
import os
import time
import traceback
import signal
from typing import Optional, Dict, Any, List, TypedDict
import threading
import requests
import json
import logging
from queue import Queue, Empty
from termcolor import colored
from .batch import LogBatch
from .constants import COMPACT_TS_KEY, COMPACT_TRACE_ID_KEY, COMPACT_MESSAGE_KEY, COMPACT_LEVEL_KEY, LEVEL_KEY, TRACE_ID_KEY, MESSAGE_KEY, TS_KEY, LogEntry

fallback_logger = logging.getLogger('treebeard')
fallback_logger.propagate = False
if not fallback_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)-7s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    fallback_logger.addHandler(handler)

fallback_logger.setLevel(logging.DEBUG)

LEVEL_COLORS = {
    'trace': 'white',
    'debug': 'dark_grey',
    'info': 'green',
    'warning': 'yellow',
    'error': 'red',
    'critical': 'red'
}

has_warned = False
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
                fallback_logger.error(
                    f"Unexpected error in log sender: {str(e)}")
            finally:
                _send_queue.task_done()

    def stop(self):
        self._stop_event.set()
        _send_queue.put(None)


_worker = LogSenderWorker()
_worker.start()

# Handle shutdown signals


def _handle_shutdown(sig, frame):
    fallback_logger.info("Shutdown signal received, stopping log sender...")
    _worker.stop()
    _worker.join()


signal.signal(signal.SIGINT, _handle_shutdown)
signal.signal(signal.SIGTERM, _handle_shutdown)


class Treebeard:
    _instance: Optional['Treebeard'] = None
    _initialized = False
    _api_key: Optional[str] = None
    _debug_mode: bool = False
    _batch: Optional[LogBatch] = None
    _endpoint: Optional[str] = None
    _env: Optional[str] = None

    def __new__(cls, endpoint: Optional[str] = None, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._api_key = None
            cls._instance._debug_mode = False
            cls._instance._batch = None
            cls._instance._endpoint = None
        return cls._instance

    def __init__(self, endpoint: Optional[str] = None, batch_size: int = 100, batch_age: float = 5.0):
        if Treebeard._initialized:
            return
        self._batch = LogBatch(max_size=batch_size, max_age=batch_age)
        self._env = os.getenv('ENV') or "production"
        if not self._initialized and endpoint is not None:
            self._endpoint = endpoint
            self._using_fallback = False

    def config(self, api_key: Optional[str] = None, endpoint: Optional[str] = None, batch_size: int = 100, batch_age: float = 5.0) -> None:
        self.api_key = api_key or os.getenv('TREEBEARD_API_KEY')
        self._endpoint = endpoint or os.getenv(
            'TREEBEARD_ENDPOINT') or 'https://api.treebeardhq.com/logs/batch'
        self._using_fallback = False
        self._batch = LogBatch(max_size=batch_size, max_age=batch_age)
        return self

    @classmethod
    def init(cls, api_key: Optional[str] = None, **config: Any) -> None:
        if cls._initialized:
            fallback_logger.warning(
                "Treebeard is already initialized - ignoring config")
            return

        instance = cls()

        if api_key is None or not api_key.strip():
            fallback_logger.warning(
                "No API key provided - logs will be output to standard Python logger")
            instance._using_fallback = True
        else:
            instance._api_key = api_key.strip()
            instance._using_fallback = False
            endpoint = config.get('endpoint')
            if not endpoint:
                raise ValueError(
                    "endpoint must be provided when using API key")

            instance._endpoint = endpoint
            instance._batch = LogBatch(
                max_size=config.get('batch_size', 100),
                max_age=config.get('batch_age', 5.0)
            )

        instance._debug_mode = bool(config.get('debug_mode', False))
        cls._initialized = True

    @property
    def api_key(self) -> Optional[str]:
        return self._api_key

    @property
    def debug_mode(self) -> bool:
        return self._debug_mode

    @classmethod
    def reset(cls) -> None:
        if cls._instance is not None:
            cls._instance._api_key = None
            cls._instance._debug_mode = False
            cls._instance._endpoint = None
            cls._instance._batch = None
            cls._initialized = False

    def add(self, log_entry: Any) -> None:

        if self._using_fallback:
            key = os.getenv('TREEBEARD_API_KEY')
            if key:
                # reset env if we've found a key, just to make sure
                self._env = os.getenv('ENV') or "production"
                self._endpoint = os.getenv(
                    'TREEBEARD_ENDPOINT') or 'https://api.treebeardhq.com/logs'
                self._using_fallback = False
                self._api_key = key
                self._initialized = True

        global has_warned
        if not self._initialized:
            if not has_warned:
                fallback_logger.warning(
                    "Treebeard is not initialized - logs will be output to standard Python logger")
                has_warned = True
            self._log_to_fallback(log_entry)
            return

        log_entry = self.augment(log_entry)

        if not self._using_fallback and self._batch.add(self.format(log_entry)):
            self.flush()

        if self._using_fallback or self._env == "development":
            self._log_to_fallback(log_entry)

    def format(self, log_entry: LogEntry) -> LogEntry:
        result: LogEntry = {}
        result[COMPACT_TS_KEY] = log_entry.get(
            TS_KEY, round(time.time() * 1000))
        result[COMPACT_TRACE_ID_KEY] = log_entry.get(TRACE_ID_KEY, '')
        result[COMPACT_MESSAGE_KEY] = log_entry.get(MESSAGE_KEY, '')
        result[COMPACT_LEVEL_KEY] = log_entry.get(LEVEL_KEY, 'debug')
        result['props'] = log_entry.get('props', {})
        return result

    def augment(self, log_entry: Any) -> None:
        log_entry['ts'] = log_entry.get('ts', round(time.time() * 1000))
        return log_entry

    def _log_to_fallback(self, log_entry: Dict[str, Any]) -> None:
        level = log_entry.get('level', 'info')
        message = log_entry.pop('message', '')
        error = log_entry.pop('error', None)
        trace_id = log_entry.pop('trace_id', None)
        ts = log_entry.pop('ts', None)

        metadata = {k: v for k, v in log_entry.items() if k != 'level'}

        metadata_str = ''
        if metadata:
            formatted_metadata = self.dict_to_yaml_like(metadata)
            metadata_str = f"{colored(formatted_metadata, 'dark_grey')}"

        color = LEVEL_COLORS.get(level, 'white')
        formatted_message = colored(f"[{trace_id}] {message}", color)
        full_message = formatted_message + \
            ('\n' + metadata_str if metadata_str else '')

        level_map = {
            'trace': logging.DEBUG,
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
        }
        log_level = level_map.get(level, logging.INFO)

        fallback_logger.log(log_level, full_message)

        if error and isinstance(error, Exception):
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
        data = json.dumps({'logs': logs})

        def send_request():
            max_retries = 3
            delay = 1  # seconds
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        self._endpoint, headers=headers, data=data)
                    if response.ok:
                        return
                    else:
                        fallback_logger.warning(
                            f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
                except Exception as e:
                    fallback_logger.warning(
                        f"Attempt {attempt+1} error: {str(e)}")
                time.sleep(delay)
            fallback_logger.error("All attempts to send logs failed.")

        _send_queue.put(send_request)
