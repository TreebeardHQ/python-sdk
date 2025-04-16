from typing import TypedDict, Optional, Dict, Any

TRACE_ID_KEY = "trace_id"
MESSAGE_KEY = "message"
LEVEL_KEY = "level"
ERROR_KEY = "error"
TS_KEY = "ts"
FILE_KEY = "file"
LINE_KEY = "line"
TRACEBACK_KEY = "traceback"
TRACE_NAME_KEY = "tb_trace_name"


COMPACT_TRACE_ID_KEY = "tid"
COMPACT_MESSAGE_KEY = "msg"
COMPACT_LEVEL_KEY = "lvl"
COMPACT_TS_KEY = "ts"
COMPACT_FILE_KEY = "fl"
COMPACT_LINE_KEY = "ln"
COMPACT_TRACEBACK_KEY = "tb"
COMPACT_TRACE_NAME_KEY = "tn"


# Trace markers
TRACE_START_MARKER = "tb_trace_start"
TRACE_COMPLETE_SUCCESS_MARKER = "tb_trace_complete_success"
TRACE_COMPLETE_ERROR_MARKER = "tb_trace_complete_error"


class LogEntry(TypedDict, total=False):
    """A typed dictionary representing a log entry."""
    lvl: str
    tid: str
    msg: str
    ts: Optional[float]
    props: Optional[Dict[str, Any]]
