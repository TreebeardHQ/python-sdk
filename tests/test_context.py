"""
Tests for the LoggingContext functionality.
"""
import threading

import pytest

from treebeardhq.context import LoggingContext


@pytest.mark.usefixtures("reset_context", "clean_modules")
class TestLoggingContext:
    """Tests for LoggingContext functionality."""

    def test_context_isolation_between_threads(self):
        """Test that context is isolated between threads."""
        LoggingContext.set('main_value', 'main_thread')

        thread_value = None

        def thread_func():
            nonlocal thread_value
            # This thread should have its own empty context
            thread_value = LoggingContext.get('main_value')
            # Set a different value in this thread
            LoggingContext.set('thread_value', 'worker_thread')

        thread = threading.Thread(target=thread_func)
        thread.start()
        thread.join()

        # The thread should not see the main thread's value
        assert thread_value is None
        # Main thread should not see the thread's value
        assert LoggingContext.get('thread_value') is None
        # Main thread should still have its value
        assert LoggingContext.get('main_value') == 'main_thread'

    @pytest.mark.gevent
    def test_context_isolation_in_greenlet(self):
        """Test that context is isolated between greenlets."""
        import gevent.monkey
        gevent.monkey.patch_thread()  # Explicitly patch threading
        import gevent
        from gevent import Greenlet

        LoggingContext._thread_local = None  # Force re-init
        LoggingContext._context_type = None

        LoggingContext.set('main_value', 'main_greenlet')
        greenlet_value = None

        def greenlet_func():
            nonlocal greenlet_value
            # This greenlet should have its own empty context
            greenlet_value = LoggingContext.get('main_value')
            # Set a different value in this greenlet
            LoggingContext.set('greenlet_value', 'worker_greenlet')

        g = Greenlet(greenlet_func)
        g.start()
        g.join()

        # The greenlet should not see the main context's value
        assert greenlet_value is None
        # Main context should not see the greenlet's value
        assert LoggingContext.get('greenlet_value') is None
        # Main context should still have its value
        assert LoggingContext.get('main_value') == 'main_greenlet'

    def test_set_and_get(self):
        """Test basic setting and getting values."""
        LoggingContext.set('key1', 'value1')
        LoggingContext.set('key2', {'nested': 'data'})

        assert LoggingContext.get('key1') == 'value1'
        assert LoggingContext.get('key2') == {'nested': 'data'}
        assert LoggingContext.get('missing_key') is None
        assert LoggingContext.get('missing_key', 'default') == 'default'

    def test_clear(self):
        """Test clearing the context."""
        LoggingContext.set('key1', 'value1')
        LoggingContext.set('key2', 'value2')

        LoggingContext.clear()

        assert LoggingContext.get('key1') is None
        assert LoggingContext.get('key2') is None

    def test_get_all(self):
        """Test getting all context data."""
        LoggingContext.set('key1', 'value1')
        LoggingContext.set('key2', 123)

        all_data = LoggingContext.get_all()

        assert all_data == {'key1': 'value1', 'key2': 123}

        # Modifying the returned data should not affect the context
        all_data['key3'] = 'new_value'
        assert LoggingContext.get('key3') is None
