
# constants.py (or in the same file, near the other defaults)
import threading
from treebeardhq.internal_utils.fallback_logger import sdk_logger


DEFAULT_FLUSH_INTERVAL = 30.0          # seconds


class FlushTimerWorker(threading.Thread):
    def __init__(self, treebeard_ref: any, interval: float = DEFAULT_FLUSH_INTERVAL):
        super().__init__(daemon=True)
        self._tb = treebeard_ref
        self._interval = interval
        self._stop = threading.Event()

    def run(self):
        while not self._stop.wait(self._interval):        # sleeps atomically
            try:
                # Do nothing if the SDK was never fully initialised
                if not self._tb._initialized:
                    continue

                # Don’t waste an HTTP call if there’s nothing to send
                result = self._tb.flush()      # add is_empty() below
                sdk_logger.info(
                    f"Flush timer worker: flushed logs, result: {result}")

            except Exception as e:                        # never kill the thread
                sdk_logger.error("flush-timer error", exc_info=e)

    def stop(self):
        self._stop.set()
