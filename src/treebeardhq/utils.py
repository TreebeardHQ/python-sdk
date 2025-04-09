"""Utility functions for Treebeard."""
import sys
from enum import Enum
from typing import Tuple

# try:
#     import eventlet
#     HAS_EVENTLET = True
# except ImportError:
#     HAS_EVENTLET = False

# try:
#     import gevent
#     HAS_GEVENT = True
# except ImportError:
#     HAS_GEVENT = False


class ThreadingMode(Enum):
    THREAD = "thread"
    EVENTLET = "eventlet"
    GEVENT = "gevent"


def detect_threading_mode() -> Tuple[ThreadingMode, str]:
    """Detect the appropriate threading mode for the current environment.

    Returns:
        Tuple of (ThreadingMode enum, reason string)
    """
    # # Check if we're explicitly using eventlet
    # if 'eventlet.green.threading' in sys.modules:
    #     return ThreadingMode.EVENTLET, "eventlet.green.threading module detected"

    # # Check if we're explicitly using gevent
    # if 'gevent.monkey' in sys.modules and sys.modules['gevent.monkey'].is_module_patched('threading'):
    #     return ThreadingMode.GEVENT, "gevent monkey-patched threading detected"

    return ThreadingMode.THREAD, "using standard Python threading"
