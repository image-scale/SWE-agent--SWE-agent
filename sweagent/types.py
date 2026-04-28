from __future__ import annotations

from typing import Any, TypedDict


class HistoryEntry(TypedDict, total=False):
    role: str
    content: str
    message_type: str
    agent: str
    action: str
    tags: list[str]


class History(list):
    """A list of history entries representing conversation history."""

    def __init__(self, entries: list[dict[str, Any]] | None = None):
        if entries is None:
            entries = []
        super().__init__(entries)


class AgentRunResult:
    """Result of an agent run."""

    def __init__(
        self,
        info: dict[str, Any] | None = None,
        trajectory: list[dict[str, Any]] | None = None,
    ):
        self.info = info or {}
        self.trajectory = trajectory or []
