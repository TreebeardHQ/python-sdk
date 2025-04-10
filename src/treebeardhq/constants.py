from typing import TypedDict, Optional, Dict, Any

TRACE_ID_KEY = "trace_id"
MESSAGE_KEY = "message"
LEVEL_KEY = "level"
ERROR_KEY = "error"
TS_KEY = "ts"
FILE_KEY = "file"
LINE_KEY = "line"


COMPACT_TRACE_ID_KEY = "tid"
COMPACT_MESSAGE_KEY = "msg"
COMPACT_LEVEL_KEY = "lvl"
COMPACT_TS_KEY = "ts"
COMPACT_FILE_KEY = "fl"
COMPACT_LINE_KEY = "ln"


class LogEntry(TypedDict, total=False):
    """A typed dictionary representing a log entry."""
    lvl: str
    tid: str
    msg: str
    ts: Optional[float]
    props: Optional[Dict[str, Any]]
