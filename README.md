# Treebeard

Treebeard is a Python library for efficient log forwarding with support for trace contexts and batched logging.

## Installation

```bash
pip install treebeardhq
```

## Quick Start

```python
from treebeardhq import Treebeard, Log

# Initialize Treebeard with your API key
Treebeard.init(
    api_key="your-api-key",
    endpoint="https://your-logging-endpoint.com/logs"
)
# Start a trace context

try:
    # Log different severity levels with optional metadata
    Log.info("Starting image processing", image_format="PNG")

    # Some business logic here...

    Log.debug("Image validation", data={"dimensions": [1920, 1080], "color_space": "RGB"})

    # More logic...

    Log.info("Image processed successfully", output_size_kb=256)

except Exception as e:
    Log.error("Processing failed", error=str(e))


```

## Logging Levels

Treebeard supports multiple logging levels:

```python
Log.debug("Debug information")
Log.info("General information")
Log.warning("Warning message")
Log.error("Error message")
```

## Adding Context Data

You can add metadata to your logs in two ways:

```python
)

# Using keyword arguments
Log.info("User action",
    user_id="123",
    action="login",
    ip="192.168.1.1"
)
```

## Trace Contexts

Trace contexts help you group related logs together:

```python
# Start a new trace context

# All logs within this context will include the trace ID
Log.info("Processing payment")
Log.debug("Validating card details")


```

## Configuration Options

When initializing Treebeard, you can configure several options:

```python
Treebeard.init(
    api_key="your-api-key",
    endpoint="https://your-logging-endpoint.com/logs",
    debug_mode=True,  # Enable debug output
    batch_size=100,   # Max logs per batch
    batch_age=5.0,    # Max seconds before sending a batch
    threading_mode="thread"  # 'thread', 'eventlet', or 'gevent'
)
```

## Thread Safety

Treebeard is thread-safe and supports different threading modes:

- Standard Python threading (default)
- Eventlet
- Gevent

## License

MIT License - see LICENSE file for details.
