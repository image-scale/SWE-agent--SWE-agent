"""History processors for managing conversation context.

History processors transform the conversation history before it's sent to
the language model. This allows for operations like:
- Eliding old observations to save context
- Adding cache control markers for prompt caching
- Tagging specific tool call observations
- Removing regex patterns from content
"""

import copy
import re
from abc import abstractmethod
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from codeagent.types import History, HistoryItem


class HistoryProcessor(Protocol):
    """Protocol for history processors."""

    @abstractmethod
    def __call__(self, history: History) -> History:
        """Process and return the modified history."""
        raise NotImplementedError


def _get_content_text(entry: HistoryItem) -> str:
    """Extract text content from a history item."""
    if isinstance(entry["content"], str):
        return entry["content"]
    assert len(entry["content"]) == 1, "Expected single message in content"
    return entry["content"][0]["text"]


def _set_content_text(entry: HistoryItem, text: str) -> None:
    """Set the text content of a history item."""
    if isinstance(entry["content"], str):
        entry["content"] = text
    else:
        assert len(entry["content"]) == 1, "Expected single message in content"
        entry["content"][0]["text"] = text


def _get_content_stats(entry: HistoryItem) -> tuple[int, int]:
    """Get line count and image count from a history item."""
    if isinstance(entry["content"], str):
        return len(entry["content"].splitlines()), 0
    n_text_lines = sum(
        len(item["text"].splitlines())
        for item in entry["content"]
        if item.get("type") == "text"
    )
    n_images = sum(1 for item in entry["content"] if item.get("type") == "image_url")
    return n_text_lines, n_images


def _clear_cache_control(entry: HistoryItem) -> None:
    """Remove cache_control from a history item."""
    if isinstance(entry["content"], list):
        for item in entry["content"]:
            item.pop("cache_control", None)
    entry.pop("cache_control", None)


def _set_cache_control(entry: HistoryItem) -> None:
    """Add cache_control to a history item."""
    if not isinstance(entry["content"], list):
        entry["content"] = [
            {
                "type": "text",
                "text": _get_content_text(entry),
                "cache_control": {"type": "ephemeral"},
            }
        ]
    else:
        entry["content"][0]["cache_control"] = {"type": "ephemeral"}
    if entry["role"] == "tool":
        entry["content"][0].pop("cache_control", None)
        entry["cache_control"] = {"type": "ephemeral"}


class DefaultHistoryProcessor(BaseModel):
    """No-op processor that returns history unchanged.

    Used as the default when no processing is needed.
    """

    type: Literal["default"] = "default"
    model_config = ConfigDict(extra="forbid")

    def __call__(self, history: History) -> History:
        """Return history unchanged."""
        return history


class LastNObservations(BaseModel):
    """Elides all but the last N observations.

    Older observations are replaced with a summary indicating how many
    lines were omitted. The first observation (instance template) is
    never removed.

    This helps manage context window size while preserving recent context.
    """

    n: int
    """Number of observations to keep."""

    polling: int = 1
    """Steps between updating the kept observations (for cache efficiency)."""

    always_remove_output_for_tags: set[str] = {"remove_output"}
    """Tags that cause observations to be elided regardless of position."""

    always_keep_output_for_tags: set[str] = {"keep_output"}
    """Tags that preserve observations regardless of position."""

    type: Literal["last_n_observations"] = "last_n_observations"
    model_config = ConfigDict(extra="forbid")

    @field_validator("n")
    def validate_n(cls, n: int) -> int:
        if n <= 0:
            msg = "n must be a positive integer"
            raise ValueError(msg)
        return n

    def _get_omit_indices(self, history: History) -> list[int]:
        """Get indices of observations that should be elided."""
        observation_indices = [
            idx
            for idx, entry in enumerate(history)
            if entry.get("message_type") == "observation"
            and not entry.get("is_demo", False)
        ]
        last_removed_idx = max(
            0, (len(observation_indices) // self.polling) * self.polling - self.n
        )
        return observation_indices[1:last_removed_idx]

    def __call__(self, history: History) -> History:
        """Process history, eliding old observations."""
        new_history = []
        omit_content_idxs = self._get_omit_indices(history)

        for idx, entry in enumerate(history):
            tags = set(entry.get("tags", []))
            should_keep = (
                (idx not in omit_content_idxs)
                or (tags & self.always_keep_output_for_tags)
            ) and not (tags & self.always_remove_output_for_tags)

            if should_keep:
                new_history.append(entry)
            else:
                data = entry.copy()
                num_text_lines, num_images = _get_content_stats(data)
                data["content"] = f"Old environment output: ({num_text_lines} lines omitted)"
                if num_images > 0:
                    data["content"] += f" ({num_images} images omitted)"
                new_history.append(data)

        return new_history


class TagToolCallObservations(BaseModel):
    """Adds tags to history items for specific tool calls.

    Useful for marking certain tool outputs for special processing,
    like keeping edit outputs visible.
    """

    type: Literal["tag_tool_call_observations"] = "tag_tool_call_observations"

    tags: set[str] = {"keep_output"}
    """Tags to add to matching observations."""

    function_names: set[str] = set()
    """Only consider observations from tools with these names."""

    model_config = ConfigDict(extra="forbid")

    def _add_tags(self, entry: HistoryItem) -> None:
        """Add configured tags to an entry."""
        existing_tags = set(entry.get("tags", []))
        existing_tags.update(self.tags)
        entry["tags"] = list(existing_tags)

    def _should_add_tags(self, entry: HistoryItem) -> bool:
        """Check if entry matches criteria for tagging."""
        if entry.get("message_type") != "action":
            return False
        function_calls = entry.get("tool_calls", [])
        if not function_calls:
            return False
        function_names = {call["function"]["name"] for call in function_calls}
        return bool(self.function_names & function_names)

    def __call__(self, history: History) -> History:
        """Process history, adding tags to matching entries."""
        for entry in history:
            if self._should_add_tags(entry):
                self._add_tags(entry)
        return history


class CacheControlHistoryProcessor(BaseModel):
    """Adds cache control markers for prompt caching.

    Adds cache_control to the last N user/tool messages and removes
    it from all others. This optimizes API costs when using models
    that support prompt caching.
    """

    type: Literal["cache_control"] = "cache_control"

    last_n_messages: int = 2
    """Number of recent messages to mark for caching."""

    last_n_messages_offset: int = 0
    """Offset from the end to start marking (for special cases)."""

    tagged_roles: list[str] = ["user", "tool"]
    """Roles that should receive cache control markers."""

    model_config = ConfigDict(extra="forbid")

    def __call__(self, history: History) -> History:
        """Process history, adding cache control markers."""
        new_history = []
        n_tagged = 0

        for i_entry, entry in enumerate(reversed(history)):
            _clear_cache_control(entry)
            should_tag = (
                n_tagged < self.last_n_messages
                and entry["role"] in self.tagged_roles
                and i_entry >= self.last_n_messages_offset
            )
            if should_tag:
                _set_cache_control(entry)
                n_tagged += 1
            new_history.append(entry)

        return list(reversed(new_history))


class RemoveRegex(BaseModel):
    """Removes content matching regex patterns from history.

    Useful for removing verbose output like diff blocks that
    clutter the context without adding value for subsequent steps.
    """

    remove: list[str] = ["<diff>.*</diff>"]
    """Regex patterns to remove from history content."""

    keep_last: int = 0
    """Number of recent history items to leave unchanged."""

    type: Literal["remove_regex"] = "remove_regex"
    model_config = ConfigDict(extra="forbid")

    def __call__(self, history: History) -> History:
        """Process history, removing matching content."""
        new_history = []

        for i_entry, entry in enumerate(reversed(history)):
            entry = copy.deepcopy(entry)
            if i_entry < self.keep_last:
                new_history.append(entry)
            else:
                if isinstance(entry["content"], list):
                    for item in entry["content"]:
                        if item.get("type") == "text":
                            for pattern in self.remove:
                                item["text"] = re.sub(
                                    pattern, "", item["text"], flags=re.DOTALL
                                )
                else:
                    for pattern in self.remove:
                        entry["content"] = re.sub(
                            pattern, "", entry["content"], flags=re.DOTALL
                        )
                new_history.append(entry)

        return list(reversed(new_history))
