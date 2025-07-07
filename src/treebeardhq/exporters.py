"""
Export functionality for sending logs, objects, and spans to the Treebeard API.
"""
import json
import threading
import time
from queue import Queue
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import requests

from .internal_utils.fallback_logger import sdk_logger

if TYPE_CHECKING:
    from .spans import Span


class LogSenderWorker(threading.Thread):
    """Worker thread to process sending requests asynchronously."""
    
    def __init__(self, send_queue: Queue):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._send_queue = send_queue

    def run(self) -> None:
        while True:
            send_fn = self._send_queue.get()
            if send_fn is None:  # shutdown signal
                break
            try:
                send_fn()
            except Exception as e:
                sdk_logger.error(
                    f"Unexpected error in log sender: {str(e)}")
            finally:
                self._send_queue.task_done()

    def stop(self) -> None:
        self._stop_event.set()
        self._send_queue.put(None)


class TreebeardExporter:
    """Handles exporting logs, objects, and spans to the Treebeard API."""
    
    def __init__(
        self, api_key: str, endpoint: str, objects_endpoint: str, 
        spans_endpoint: Optional[str] = None, project_name: Optional[str] = None
    ):
        self._api_key = api_key
        self._endpoint = endpoint
        self._objects_endpoint = objects_endpoint
        self._spans_endpoint = spans_endpoint or endpoint.replace('/logs/batch', '/spans/batch')
        self._project_name = project_name
        self._send_queue: Queue = Queue()
        self._worker: Optional[LogSenderWorker] = None
        self._worker_started = False
        
    def start_worker(self) -> None:
        """Start the background worker thread if not already started."""
        if not self._worker_started:
            if not self._worker or not self._worker.is_alive():
                self._worker = LogSenderWorker(self._send_queue)
                self._worker.start()
                sdk_logger.info("Treebeard log worker started.")
            self._worker_started = True
            
    def stop_worker(self) -> None:
        """Stop the background worker thread."""
        if self._worker and self._worker.is_alive():
            self._worker.stop()
            self._worker.join(timeout=10)
            self._worker_started = False
            
    def send_logs_async(
        self, logs: List[Any], config_version: Optional[int] = None, 
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Queue logs to be sent asynchronously."""
        def send_request():
            self._send_logs(logs, config_version, update_callback)
        
        self._send_queue.put(send_request)
        
    def send_objects_async(
        self, objects: List[Dict[str, Any]], config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Queue objects to be sent asynchronously."""
        def send_request():
            self._send_objects(objects, config_version, update_callback)
            
        self._send_queue.put(send_request)
        
    def send_spans_async(
        self, spans: List["Span"], config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Queue spans to be sent asynchronously."""
        def send_request():
            self._send_spans(spans, config_version, update_callback)
            
        self._send_queue.put(send_request)
        
    def _send_logs(self, logs: List[Any], config_version: Optional[int] = None,
                   update_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """Send logs to the Treebeard API."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }
        data = json.dumps({
            'logs': logs,
            'project_name': self._project_name,
            "v": config_version,
            "sdk_version": 2
        })

        max_retries = 3
        delay = 1  # seconds
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self._endpoint, headers=headers, data=data)
                if response.ok:
                    sdk_logger.debug(
                        f"Logs sent successfully. logs sent: {len(logs)}")

                    result = response.json()

                    # we get an updated config if the server has a later config version than we
                    # sent it
                    if (
                        isinstance(result, dict) and result.get('updated_config') 
                        and update_callback
                    ):
                        update_callback(result.get('updated_config'))

                    return result
                else:
                    sdk_logger.warning(
                        f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
            except Exception as e:
                sdk_logger.error("error while sending logs", exc_info=e)
            time.sleep(delay)
        sdk_logger.error("All attempts to send logs failed.")

    def _send_objects(self, objects: List[Dict[str, Any]], config_version: Optional[int] = None,
                      update_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """Send object registrations to the API."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }
        data = json.dumps({
            'objects': objects,
            'project_name': self._project_name,
            "v": config_version,
            "sdk_version": 2
        })

        max_retries = 3
        delay = 1  # seconds
        for attempt in range(max_retries):
            try:
                sdk_logger.warning(
                    f"Sending objects to {self._objects_endpoint}")
                response = requests.post(
                    self._objects_endpoint, headers=headers, data=data)
                if response.ok:
                    sdk_logger.debug(
                        f"Objects sent successfully. objects sent: {len(objects)}")

                    result = response.json()

                    # we get an updated config if the server has a later config version than we
                    # sent it
                    if (
                        isinstance(result, dict) and result.get('updated_config') 
                        and update_callback
                    ):
                        update_callback(result.get('updated_config'))

                    return result
                else:
                    sdk_logger.warning(
                        f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
            except Exception as e:
                sdk_logger.error("error while sending objects", exc_info=e)
            time.sleep(delay)
        sdk_logger.error("All attempts to send objects failed.")

    def _send_spans(
        self, spans: List["Span"], config_version: Optional[int] = None,
        update_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        """Send spans to the Treebeard API in OpenTelemetry format."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self._api_key}'
        }
        
        # Convert spans to OpenTelemetry format
        resource_spans = self._format_spans_for_otel(spans)
        
        data = json.dumps({
            'resourceSpans': resource_spans,
            'project_name': self._project_name,
            "v": config_version,
            "sdk_version": 2
        })

        max_retries = 3
        delay = 1  # seconds
        for attempt in range(max_retries):
            try:
                sdk_logger.debug(f"Sending spans to {self._spans_endpoint}")
                response = requests.post(
                    self._spans_endpoint, headers=headers, data=data)
                if response.ok:
                    sdk_logger.debug(
                        f"Spans sent successfully. spans sent: {len(spans)}")

                    result = response.json()

                    # we get an updated config if the server has a later config version than we
                    # sent it
                    if (
                        isinstance(result, dict) and result.get('updated_config') 
                        and update_callback
                    ):
                        update_callback(result.get('updated_config'))

                    return result
                else:
                    sdk_logger.warning(
                        f"Attempt {attempt+1} failed: {response.status_code} - {response.text}")
            except Exception as e:
                sdk_logger.error("error while sending spans", exc_info=e)
            time.sleep(delay)
        sdk_logger.error("All attempts to send spans failed.")

    def _format_spans_for_otel(self, spans: List["Span"]) -> List[Dict[str, Any]]:
        """Format spans into OpenTelemetry ResourceSpans structure."""
        if not spans:
            return []
        
        # Group spans by service (project) name
        scope_spans = []
        otel_spans = []
        
        for span in spans:
            otel_spans.append(span.to_otel_dict())
        
        scope_spans.append({
            "scope": {
                "name": "treebeard-python-sdk",
                "version": "2.0"
            },
            "spans": otel_spans
        })
        
        # Create resource with service name
        resource_attributes = []
        if self._project_name:
            resource_attributes.append({
                "key": "service.name",
                "value": {"stringValue": self._project_name}
            })
        
        return [{
            "resource": {
                "attributes": resource_attributes
            },
            "scopeSpans": scope_spans
        }]