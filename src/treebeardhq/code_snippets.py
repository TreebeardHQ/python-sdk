"""Code snippet extraction for exception frames."""

import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict


class FrameInfo(TypedDict):
    """Information extracted from a single frame."""

    filename: str
    lineno: int
    function: str
    code_snippet: List[str]
    context_line_numbers: List[int]
    error_line_index: int
    locals: Optional[Dict[str, str]]


class CodeSnippetExtractor:
    """Extracts code snippets from exception tracebacks."""

    def __init__(
        self,
        context_lines: int = 5,
        max_frames: int = 50,
        capture_locals: bool = False,
        exclude_patterns: Optional[List[str]] = None,
    ):
        """Initialize the code snippet extractor.

        Args:
            context_lines: Number of lines to capture before and after error line
            max_frames: Maximum number of frames to process
            capture_locals: Whether to capture local variables
            exclude_patterns: List of file patterns to exclude
        """
        self.context_lines = context_lines
        self.max_frames = max_frames
        self.capture_locals = capture_locals
        self.exclude_patterns = exclude_patterns or []
        self._file_cache: Dict[str, List[str]] = {}

    def extract_from_exception(self, exception: Exception) -> List[FrameInfo]:
        """Extract code snippets from an exception's traceback.

        Args:
            exception: The exception to extract snippets from

        Returns:
            List of frame information with code snippets
        """
        if not exception.__traceback__:
            return []

        frames: List[FrameInfo] = []
        tb_frames = traceback.extract_tb(exception.__traceback__)

        # Limit the number of frames
        tb_frames_list = list(tb_frames)[-self.max_frames :]

        for frame_summary in tb_frames_list:
            if self._should_exclude_file(frame_summary.filename):
                continue

            frame_info = self._extract_frame_info(frame_summary)
            if frame_info:
                frames.append(frame_info)

        return frames

    def _should_exclude_file(self, filename: str) -> bool:
        """Check if a file should be excluded based on patterns.

        Args:
            filename: The file path to check

        Returns:
            True if file should be excluded
        """
        # Skip Python internals
        if filename.startswith("<") and filename.endswith(">"):
            return True

        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if pattern in filename:
                return True

        return False

    def _extract_frame_info(self, frame: traceback.FrameSummary) -> Optional[FrameInfo]:
        """Extract information from a single frame.

        Args:
            frame: The frame summary to process

        Returns:
            Frame information or None if extraction fails
        """
        try:
            lines = self._read_source_lines(frame.filename)
            if not lines:
                return None

            # Calculate line range
            lineno = frame.lineno
            if lineno is None or lineno < 1 or lineno > len(lines):
                return None

            start_line = max(1, lineno - self.context_lines)
            end_line = min(len(lines), lineno + self.context_lines)

            # Extract code snippet
            code_snippet = []
            context_line_numbers = []
            error_line_index = -1

            for i, line_num in enumerate(range(start_line, end_line + 1)):
                line = lines[line_num - 1].rstrip()
                code_snippet.append(line)
                context_line_numbers.append(line_num)

                if line_num == lineno:
                    error_line_index = i

            # Extract locals if requested and available
            locals_dict = None
            if self.capture_locals and hasattr(frame, "locals"):
                locals_dict = self._serialize_locals(frame.locals)

            return FrameInfo(
                filename=frame.filename,
                lineno=lineno,  # We've already checked that lineno is not None above
                function=frame.name,
                code_snippet=code_snippet,
                context_line_numbers=context_line_numbers,
                error_line_index=error_line_index,
                locals=locals_dict,
            )

        except Exception:
            # If we can't read the source, return minimal info
            frame_lineno = frame.lineno if frame.lineno is not None else 0
            return FrameInfo(
                filename=frame.filename,
                lineno=frame_lineno,
                function=frame.name,
                code_snippet=[],
                context_line_numbers=[],
                error_line_index=-1,
                locals=None,
            )

    def _read_source_lines(self, filename: str) -> List[str]:
        """Read source lines from a file with caching.

        Args:
            filename: Path to the source file

        Returns:
            List of source lines or empty list if file can't be read
        """
        if filename in self._file_cache:
            return self._file_cache[filename]

        try:
            path = Path(filename)
            if not path.exists() or not path.is_file():
                return []

            # Check file size to avoid reading huge files
            if path.stat().st_size > 1024 * 1024:  # 1MB limit
                return []

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            self._file_cache[filename] = lines
            return lines

        except Exception:
            return []

    def _serialize_locals(
        self, locals_dict: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, str]]:
        """Safely serialize local variables to strings.

        Args:
            locals_dict: Dictionary of local variables

        Returns:
            Serialized locals or None
        """
        if not locals_dict:
            return None

        serialized = {}
        for key, value in locals_dict.items():
            # Skip module and class references
            if key.startswith("__") or callable(value):
                continue

            try:
                # Limit string representation
                str_value = repr(value)
                if len(str_value) > 200:
                    str_value = str_value[:197] + "..."
                serialized[key] = str_value
            except Exception:
                serialized[key] = "<unprintable>"

        return serialized if serialized else None


def format_code_snippet(
    frame_info: FrameInfo, show_line_numbers: bool = True, highlight_error: bool = True
) -> str:
    """Format a code snippet for display.

    Args:
        frame_info: Frame information with code snippet
        show_line_numbers: Whether to show line numbers
        highlight_error: Whether to highlight the error line

    Returns:
        Formatted code snippet string
    """
    if not frame_info["code_snippet"]:
        return ""

    lines = []
    max_line_num = max(frame_info["context_line_numbers"])
    line_num_width = len(str(max_line_num))

    for i, (line, line_num) in enumerate(
        zip(frame_info["code_snippet"], frame_info["context_line_numbers"])
    ):
        is_error_line = i == frame_info["error_line_index"]

        if show_line_numbers:
            if is_error_line and highlight_error:
                prefix = f">{line_num:>{line_num_width}} "
            else:
                prefix = f" {line_num:>{line_num_width}} "
        else:
            prefix = "> " if is_error_line and highlight_error else "  "

        lines.append(f"{prefix}{line}")

    return "\n".join(lines)
