"""
Thread-local context for Treebeard logging.

This module provides thread-local storage for logging context,
supporting different threading models:
- Standard Python threads
- Greenlets (gevent)
- Eventlet
"""
import threading
import sys
from typing import Dict, Any, Optional, Type, ClassVar

import eventlet.corolocal
from .utils import ThreadingMode, detect_threading_mode


class LoggingContext:
    """Thread-local logging context for Treebeard.

    This class stores logging context data in thread-local storage,
    ensuring each thread/greenlet/eventlet has its own isolated context.
    """
    _thread_local: ClassVar[Any] = None
    _context_type: ClassVar[str] = None

    @classmethod
    def init(cls) -> None:
        """Initialize the thread-local storage appropriate for the environment.

        Detects the threading/concurrency model being used and sets up
        the appropriate thread-local storage mechanism.
        """
        # Only initialize once
        if cls._thread_local is not None:
            return

        threading_mode, _ = detect_threading_mode()

        if threading_mode == ThreadingMode.EVENTLET:
            import eventlet
            cls._context_type = 'eventlet'
            cls._thread_local = eventlet.corolocal.local()
        elif threading_mode == ThreadingMode.GEVENT:
            import gevent.local
            cls._context_type = 'greenlet'
            cls._thread_local = gevent.local.local()
        else:
            cls._context_type = 'thread'
            cls._thread_local = threading.local()

    @classmethod
    def get_context(cls) -> Dict[str, Any]:
        """Get the current thread-local context dictionary.

        Returns:
            A dictionary containing context data for the current thread.
        """
        if cls._thread_local is None:
            cls.init()

        if not hasattr(cls._thread_local, 'context'):
            cls._thread_local.context = {}
        return cls._thread_local.context

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set a value in the current thread's context.

        Args:
            key: The key to store the value under
            value: The value to store
        """
        context = cls.get_context()
        context[key] = value

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get a value from the current thread's context.

        Args:
            key: The key to retrieve
            default: Default value if key is not found

        Returns:
            The value associated with the key, or the default if not found
        """
        context = cls.get_context()
        return context.get(key, default)

    @classmethod
    def clear(cls) -> None:
        """Clear the current thread's context."""
        if cls._thread_local is None:
            return

        if hasattr(cls._thread_local, 'context'):
            cls._thread_local.context = {}

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all context data for the current thread.

        Returns:
            A dictionary containing all context data
        """
        return cls.get_context().copy()
