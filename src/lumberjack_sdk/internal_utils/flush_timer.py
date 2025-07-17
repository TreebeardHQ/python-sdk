
# constants.py (or in the same file, near the other defaults)
import threading

from lumberjack_sdk.internal_utils.fallback_logger import sdk_logger

DEFAULT_FLUSH_INTERVAL = 30.0          # seconds


class FlushTimerWorker(threading.Thread):
    def __init__(self, lumberjack_ref: any, interval: float = DEFAULT_FLUSH_INTERVAL):
        super().__init__(daemon=True)
        self._l = lumberjack_ref
        self._interval = interval
        self._shutdown = threading.Event()

    def run(self):
        # sleeps atomically
        while not self._shutdown.wait(self._interval):
            try:
                # Do nothing if the SDK was never fully initialised
                if not self._l._initialized:
                    continue

                # Don’t waste an HTTP call if there’s nothing to send
                result = self._l.flush()      # add is_empty() below

            except Exception as e:                        # never kill the thread
                sdk_logger.error("flush-timer error", exc_info=e)

    def stop(self):
        self._shutdown.set()
