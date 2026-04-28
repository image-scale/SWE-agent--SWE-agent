from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Flake8Error:
    """Represents a flake8 error."""

    file: str
    line: int
    column: int
    message: str

    @classmethod
    def from_line(cls, line: str) -> "Flake8Error":
        """Parse a flake8 output line into a Flake8Error."""
        # Format: file.py:line:column: error_message
        # Find the last colon before the message
        parts = line.split(":")
        if len(parts) >= 4:
            # The file path might contain colons (e.g., Windows paths)
            # So we need to be careful with parsing
            # Find the pattern: :line:col: message
            import re

            match = re.match(r"(.+):(\d+):(\d+):\s*(.+)$", line)
            if match:
                return cls(
                    file=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    message=match.group(4),
                )
        msg = f"Cannot parse flake8 line: {line}"
        raise ValueError(msg)


def format_flake8_output(
    output: str,
    previous_errors_string: str = "",
    replacement_window: tuple[int, int] = (0, 0),
    replacement_n_lines: int = 0,
    show_line_numbers: bool = True,
) -> str:
    """Format flake8 output, filtering out previous errors."""
    # Parse current errors
    current_errors: list[Flake8Error] = []
    for line in output.strip().split("\n"):
        if line.strip():
            try:
                current_errors.append(Flake8Error.from_line(line))
            except ValueError:
                pass

    # Parse previous errors
    previous_errors: list[Flake8Error] = []
    for line in previous_errors_string.strip().split("\n"):
        if line.strip():
            try:
                previous_errors.append(Flake8Error.from_line(line))
            except ValueError:
                pass

    # Adjust previous errors for line shifts
    window_start, window_end = replacement_window
    window_size = window_end - window_start + 1
    shift = replacement_n_lines - window_size

    adjusted_previous: list[Flake8Error] = []
    for err in previous_errors:
        if err.line < window_start:
            # Error is before the replacement window
            adjusted_previous.append(err)
        elif err.line > window_end:
            # Error is after the replacement window, shift it
            adjusted_previous.append(
                Flake8Error(
                    file=err.file,
                    line=err.line + shift,
                    column=err.column,
                    message=err.message,
                )
            )
        # Errors within the replacement window are dropped

    # Find new errors (not in adjusted previous)
    new_errors: list[Flake8Error] = []
    for current in current_errors:
        is_previous = False
        for prev in adjusted_previous:
            if (
                current.file == prev.file
                and current.line == prev.line
                and current.column == prev.column
                and current.message == prev.message
            ):
                is_previous = True
                break
        if not is_previous:
            new_errors.append(current)

    if not new_errors:
        return ""

    # Format output
    lines = []
    for err in new_errors:
        if show_line_numbers:
            lines.append(f"- line {err.line} col {err.column}: {err.message}")
        else:
            lines.append(f"- {err.message}")

    return "\n".join(lines)
