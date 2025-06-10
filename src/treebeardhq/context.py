"""
Thread-local context for Treebeard logging.

This module provides context storage for logging using contextvars,
which works across different concurrency models including:
- Standard Python threads
- Async/await
- Greenlets (gevent)
- Eventlet
"""
import contextvars
from typing import Any, ClassVar, Dict


class LoggingContext:
    """Context storage for Treebeard logging.

    This class stores logging context data using contextvars,
    ensuring proper context isolation across different concurrency models.
    """
    _context_var: ClassVar[contextvars.ContextVar[Dict[str, Any]]
                           ] = contextvars.ContextVar('logging_context', default={})

    @classmethod
    def get_context(cls) -> Dict[str, Any]:
        """Get the current context dictionary.

        Returns:
            A dictionary containing context data for the current context.
        """
        return cls._context_var.get()

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set a value in the current context.

        Args:
            key: The key to store the value under
            value: The value to store
        """
        context = cls.get_context().copy()
        context[key] = value
        cls._context_var.set(context)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get a value from the current context.

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
        """Clear the current context."""
        cls._context_var.set({})

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all context data for the current context.

        Returns:
            A dictionary containing all context data
        """
        return cls.get_context().copy()
