#!/usr/bin/env python
"""Example Flask application with proper Lumberjack SDK integration."""

import signal
import sys
from flask import Flask, request
from lumberjack_sdk import Lumberjack
from lumberjack_sdk.log import Log

# Create Flask app
app = Flask(__name__)

# Initialize Lumberjack SDK for Flask
# IMPORTANT: Set install_signal_handlers=False to avoid conflicts with Flask
lumberjack = Lumberjack(
    project_name="my-flask-app",
    api_key="your-api-key-here",  # Or use LUMBERJACK_API_KEY env var
    install_signal_handlers=False,  # Critical for Flask/Gunicorn compatibility
    capture_python_logger=True,
    capture_stdout=True
)

@app.before_request
def before_request():
    """Log incoming requests."""
    Log.info(f"Request: {request.method} {request.path}",
             method=request.method,
             path=request.path,
             remote_addr=request.remote_addr)

@app.after_request
def after_request(response):
    """Log response status."""
    Log.info(f"Response: {response.status_code}",
             status_code=response.status_code)
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    """Log unhandled exceptions."""
    Log.error("Unhandled exception", error=e)
    return {"error": "Internal server error"}, 500

@app.route('/')
def index():
    """Main endpoint."""
    Log.info("Index page accessed")
    return {"message": "Hello from Flask with Lumberjack!"}

@app.route('/test')
def test():
    """Test endpoint."""
    Log.debug("Debug message")
    Log.info("Info message")
    Log.warning("Warning message")
    return {"status": "ok"}

# Custom signal handler for graceful shutdown
def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    print(f"\nReceived signal {sig}, shutting down...")
    Log.info(f"Shutdown signal {sig} received")
    
    # Perform graceful shutdown of Lumberjack SDK
    lumberjack.shutdown()
    
    # Exit
    sys.exit(0)

# For development server
if __name__ == '__main__':
    # Register signal handlers for development server
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    Log.info("Flask development server starting")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    finally:
        # Ensure cleanup on exit
        lumberjack.shutdown()

# For production with Gunicorn
# Note: When using Gunicorn, add shutdown hook in gunicorn_config.py:
#
# def worker_exit(server, worker):
#     from lumberjack_sdk import Lumberjack
#     Lumberjack().shutdown()
#
# Or use the atexit handler which is automatically registered