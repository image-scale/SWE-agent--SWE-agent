from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class TextNotFound(Exception):
    """Raised when text is not found in the file."""
    pass


class WindowedFile:
    """A file viewer with windowing support."""

    def __init__(self, exit_on_exception: bool = True):
        self.exit_on_exception = exit_on_exception
        self.offset_multiplier = 1 / 4
        self._first_line = 0
        self._path: Path | None = None
        self._content: list[str] = []
        self._window = 10
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Load configuration from environment file."""
        env_file = os.getenv("SWE_AGENT_ENV_FILE", ".swe-agent-env")
        if os.path.exists(env_file):
            try:
                with open(env_file) as f:
                    data = json.load(f)
                if "CURRENT_FILE" in data:
                    self._path = Path(data["CURRENT_FILE"])
                    if self._path.exists():
                        self._content = self._path.read_text().splitlines()
                if "FIRST_LINE" in data:
                    self._first_line = int(data["FIRST_LINE"])
                if "WINDOW" in data:
                    self._window = int(data["WINDOW"])
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

    def _save_to_env(self) -> None:
        """Save configuration to environment file."""
        env_file = os.getenv("SWE_AGENT_ENV_FILE", ".swe-agent-env")
        data = {}
        if os.path.exists(env_file):
            try:
                with open(env_file) as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                pass
        data["FIRST_LINE"] = str(self._first_line)
        if self._path:
            data["CURRENT_FILE"] = str(self._path)
        with open(env_file, "w") as f:
            json.dump(data, f)

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def first_line(self) -> int:
        return self._first_line

    @first_line.setter
    def first_line(self, value: int) -> None:
        self._first_line = max(0, min(value, max(0, self.n_lines - 1)))
        self._save_to_env()

    @property
    def window(self) -> int:
        return self._window

    @property
    def n_lines(self) -> int:
        return len(self._content)

    @property
    def line_range(self) -> tuple[int, int]:
        """Get the current visible line range (0-indexed, inclusive)."""
        start = self._first_line
        end = min(self._first_line + self._window - 1, self.n_lines - 1)
        return (start, end)

    def print_window(self) -> None:
        """Print the current window of lines."""
        if not self._path:
            return

        start, end = self.line_range
        lines_above = start
        lines_below = self.n_lines - end - 1

        print(f"[File: {self._path.resolve()} ({self.n_lines} lines total)]")
        if lines_above > 0:
            print(f"({lines_above} more lines above)")

        for i in range(start, end + 1):
            if i < len(self._content):
                print(f"{i + 1}:{self._content[i]}")

        if lines_below > 0:
            print(f"({lines_below} more lines below)")

    def replace_in_window(self, old_text: str, new_text: str) -> None:
        """Replace text in the current window."""
        if not self._path:
            return

        start, end = self.line_range
        found = False

        for i in range(start, end + 1):
            if i < len(self._content) and old_text in self._content[i]:
                self._content[i] = self._content[i].replace(old_text, new_text)
                found = True
                # Adjust window to keep edited line visible
                offset = int(self._window * self.offset_multiplier)
                self._first_line = max(0, i - offset)
                break

        if not found:
            raise TextNotFound(f"Text '{old_text}' not found in current window")

        # Save the file
        if self._path:
            self._path.write_text("\n".join(self._content))
        self._save_to_env()

    def goto(self, line: int, mode: str = "top") -> None:
        """Go to a specific line number."""
        if mode == "top":
            offset = int(self._window * self.offset_multiplier)
            self._first_line = max(0, line - offset)
        else:
            self._first_line = max(0, line)

        # Ensure we don't go past the end
        max_first_line = max(0, self.n_lines - self._window)
        if self._first_line > max_first_line:
            self._first_line = max_first_line

        self._save_to_env()

    def scroll(self, lines: int) -> None:
        """Scroll by a number of lines."""
        self._first_line += lines

        # Clamp to valid range
        if self._first_line < 0:
            self._first_line = 0
        max_first_line = max(0, self.n_lines - self._window)
        if self._first_line > max_first_line:
            self._first_line = max_first_line

        self._save_to_env()
