from __future__ import annotations

from typing import Any

from sweagent.types import History


class HistoryProcessor:
    """Base class for history processors."""

    def __call__(self, history: History) -> History:
        raise NotImplementedError


class LastNObservations(HistoryProcessor):
    """Keep only the last N observations."""

    def __init__(self, n: int = 3):
        self.n = n

    def __call__(self, history: History) -> History:
        raise NotImplementedError


class TagToolCallObservations(HistoryProcessor):
    """Tag observations based on function names."""

    def __init__(self, tags: set[str], function_names: set[str]):
        self.tags = tags
        self.function_names = function_names

    def __call__(self, history: History) -> History:
        raise NotImplementedError
