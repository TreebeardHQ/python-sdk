"""Tests for log batching functionality."""
import pytest
import time
from treebeard.batch import LogBatch


@pytest.mark.usefixtures("reset_context")
class TestBatch:
    """Tests for batch functionality."""

    def test_batch_respects_max_size(self):
        """Test that batch signals flush at max size."""
        batch = LogBatch(max_size=3, max_age=1000.0)

        assert not batch.add("log1")
        assert not batch.add("log2")
        assert batch.add("log3")  # Should trigger flush

        logs = batch.get_logs()
        assert len(logs) == 3
        assert logs == ["log1", "log2", "log3"]

    def test_batch_respects_max_age(self):
        """Test that batch signals flush at max age."""
        batch = LogBatch(max_size=100, max_age=0.1)

        assert not batch.add("log1")
        time.sleep(0.2)  # Wait longer than max_age
        assert batch.add("log2")  # Should trigger flush due to age

        logs = batch.get_logs()
        assert len(logs) == 2
        assert logs == ["log1", "log2"]

    def test_batch_clear_on_get(self):
        """Test that getting logs clears the batch."""
        batch = LogBatch()

        batch.add("log1")
        batch.add("log2")

        assert len(batch.get_logs()) == 2
        assert len(batch.get_logs()) == 0  # Should be empty after get

    def test_batch_thread_safety(self):
        """Test thread safety of batch operations."""
        import threading

        batch = LogBatch(max_size=1000)

        def add_logs():
            for i in range(100):
                batch.add(f"log{i}")

        threads = [threading.Thread(target=add_logs) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        logs = batch.get_logs()
        assert len(logs) == 1000
