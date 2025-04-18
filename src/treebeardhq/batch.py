"""
Batching functionality for Treebeard logs.

This module handles the caching and batching of log entries
before they are sent to the server.
"""
from typing import List, Any, Dict
from threading import Lock
import time
from .constants import LogEntry


class LogBatch:
    """Handles batching of log entries."""

    def __init__(self, max_size: int = 100, max_age: float = 30.0):
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
