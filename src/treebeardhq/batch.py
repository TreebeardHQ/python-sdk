"""
Batching functionality for Treebeard logs, objects, and spans.

This module handles the caching and batching of log entries, objects, and spans
before they are sent to the server.
"""
import time
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, List

from .constants import LogEntry

if TYPE_CHECKING:
    from .spans import Span


class ObjectBatch:
    """Handles batching of object entries for registration."""

    def __init__(self, max_size: int = 500, max_age: float = 30.0):
        """Initialize a new ObjectBatch.

        Args:
            max_size: Maximum number of entries before auto-flush
            max_age: Maximum age in seconds before auto-flush
        """
        self._objects: List[Dict[str, Any]] = []
        self._lock = Lock()
        self._last_flush = int(time.time())
        self.max_size = max_size
        self.max_age = max_age

    def add(self, obj_entry: Dict[str, Any]) -> bool:
        """Add an object entry to the batch.

        Args:
            obj_entry: The object entry to add

        Returns:
            bool: True if batch should be flushed
        """
        with self._lock:
            self._objects.append(obj_entry)

            # Check if we should flush
            should_flush = (
                len(self._objects) >= self.max_size or
                (int(time.time()) - self._last_flush) >= self.max_age
            )

            return should_flush

    def get_objects(self) -> List[Dict[str, Any]]:
        """Get all cached objects and clear the batch.

        Returns:
            List of object entries
        """
        with self._lock:
            objects = self._objects
            self._objects = []
            self._last_flush = int(time.time())
            return objects


class LogBatch:
    """Handles batching of log entries."""

    def __init__(self, max_size: int = 500, max_age: float = 30.0):
        """Initialize a new LogBatch.

        Args:
            max_size: Maximum number of entries before auto-flush
            max_age: Maximum age in seconds before auto-flush
        """
        self._logs: List[LogEntry] = []
        self._lock = Lock()
        self._last_flush = int(time.time())
        self.max_size = max_size
        self.max_age = max_age

    def add(self, log_entry: LogEntry) -> bool:
        """Add a log entry to the batch.

        Args:
            log_entry: The log entry to add (opaque to this class)

        Returns:
            bool: True if batch should be flushed
        """
        with self._lock:
            self._logs.append(log_entry)

            # Check if we should flush
            should_flush = (
                len(self._logs) >= self.max_size or
                (int(time.time()) - self._last_flush) >= self.max_age
            )

            return should_flush

    def get_logs(self) -> List[LogEntry]:
        """Get all cached logs and clear the batch.

        Returns:
            List of log entries
        """
        with self._lock:
            logs = self._logs
            self._logs = []
            self._last_flush = int(time.time())
            return logs


class SpanBatch:
    """Handles batching of span entries."""

    def __init__(self, max_size: int = 500, max_age: float = 30.0):
        """Initialize a new SpanBatch.

        Args:
            max_size: Maximum number of entries before auto-flush
            max_age: Maximum age in seconds before auto-flush
        """
        self._spans: List["Span"] = []
        self._lock = Lock()
        self._last_flush = int(time.time())
        self.max_size = max_size
        self.max_age = max_age

    def add(self, span: "Span") -> bool:
        """Add a span to the batch.

        Args:
            span: The span to add

        Returns:
            bool: True if batch should be flushed
        """
        with self._lock:
            self._spans.append(span)

            # Check if we should flush
            should_flush = (
                len(self._spans) >= self.max_size or
                (int(time.time()) - self._last_flush) >= self.max_age
            )

            return should_flush

    def get_spans(self) -> List["Span"]:
        """Get all cached spans and clear the batch.

        Returns:
            List of spans
        """
        with self._lock:
            spans = self._spans
            self._spans = []
            self._last_flush = int(time.time())
            return spans
