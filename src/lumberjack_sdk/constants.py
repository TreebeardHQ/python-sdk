from typing import Any, Dict, Optional, TypedDict

# global reserved keys
ERROR_KEY = "error"
TS_KEY = "ts"


# v2 reserved keys
TRACE_ID_KEY_RESERVED_V2 = "tb_rv2_trace_id"
SPAN_ID_KEY_RESERVED_V2 = "tb_rv2_span_id"
MESSAGE_KEY_RESERVED_V2 = "tb_rv2_message"
LEVEL_KEY_RESERVED_V2 = "tb_rv2_level"
ERROR_KEY_RESERVED_V2 = "tb_rv2_error"
TS_KEY_RESERVED_V2 = "tb_rv2_ts"
FILE_KEY_RESERVED_V2 = "tb_rv2_file"
LINE_KEY_RESERVED_V2 = "tb_rv2_line"
FUNCTION_KEY_RESERVED_V2 = "tb_rv2_function"
TRACEBACK_KEY_RESERVED_V2 = "tb_rv2_traceback"
TRACE_NAME_KEY_RESERVED_V2 = "tb_rv2_trace_name"
SOURCE_KEY_RESERVED_V2 = "tb_rv2_source"
EXEC_TYPE_RESERVED_V2 = "tb_rv2_exec_type"
EXEC_VALUE_RESERVED_V2 = "tb_rv2_exec_value"


COMPACT_TRACE_ID_KEY = "tid"
COMPACT_SPAN_ID_KEY = "sid"
COMPACT_MESSAGE_KEY = "msg"
COMPACT_LEVEL_KEY = "lvl"
COMPACT_TS_KEY = "ts"
COMPACT_FILE_KEY = "fl"
COMPACT_LINE_KEY = "ln"
COMPACT_TRACEBACK_KEY = "tb"
COMPACT_EXEC_TYPE_KEY = "ext"
COMPACT_EXEC_VALUE_KEY = "exv"
COMPACT_TRACE_NAME_KEY = "tn"
COMPACT_SOURCE_KEY = "src"
COMPACT_FUNCTION_KEY = "fn"


# Trace markers
TRACE_START_MARKER = "tb_trace_start"
TRACE_COMPLETE_SUCCESS_MARKER = "tb_trace_complete_success"
TRACE_COMPLETE_ERROR_MARKER = "tb_trace_complete_error"

TAGS_KEY = "tb_i_tags"


class LogEntry(TypedDict, total=False):
    """A typed dictionary representing a log entry."""
    lvl: str
    tid: str
    msg: str
    fl: str
    ln: int
    tb: str
    src: str
    ts: Optional[float]
    props: Optional[Dict[str, Any]]
