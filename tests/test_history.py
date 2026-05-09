"""Tests for history processors."""

import pytest

from codeagent.types import History, HistoryItem
from codeagent.history import (
    DefaultHistoryProcessor,
    LastNObservations,
    TagToolCallObservations,
    CacheControlHistoryProcessor,
    RemoveRegex,
)


def create_history_item(
    role: str = "user",
    content: str = "test content",
    message_type: str = "observation",
    **kwargs
) -> HistoryItem:
    """Helper to create history items for testing."""
    item: HistoryItem = {
        "role": role,
        "content": content,
        "message_type": message_type,
    }
    item.update(kwargs)
    return item


class TestDefaultHistoryProcessor:
    def test_returns_history_unchanged(self):
        processor = DefaultHistoryProcessor()
        history: History = [
            create_history_item(content="first"),
            create_history_item(content="second"),
        ]
        result = processor(history)
        assert result == history
        assert len(result) == 2

    def test_empty_history(self):
        processor = DefaultHistoryProcessor()
        result = processor([])
        assert result == []


class TestLastNObservations:
    def test_keeps_last_n_observations(self):
        processor = LastNObservations(n=2)
        history: History = [
            create_history_item(content="instance template", message_type="observation"),
            create_history_item(content="obs1", message_type="observation"),
            create_history_item(content="obs2", message_type="observation"),
            create_history_item(content="obs3", message_type="observation"),
        ]
        result = processor(history)
        assert "obs1" not in result[1]["content"]
        assert "lines omitted" in result[1]["content"]
        assert result[0]["content"] == "instance template"
        assert result[-1]["content"] == "obs3"

    def test_never_removes_first_observation(self):
        processor = LastNObservations(n=1)
        history: History = [
            create_history_item(content="first obs - instance template", message_type="observation"),
            create_history_item(content="obs2", message_type="observation"),
            create_history_item(content="obs3", message_type="observation"),
        ]
        result = processor(history)
        assert result[0]["content"] == "first obs - instance template"

    def test_respects_always_keep_tags(self):
        processor = LastNObservations(
            n=1,
            always_keep_output_for_tags={"keep_output"}
        )
        history: History = [
            create_history_item(content="first", message_type="observation"),
            create_history_item(content="keep me", message_type="observation", tags=["keep_output"]),
            create_history_item(content="last", message_type="observation"),
        ]
        result = processor(history)
        assert result[1]["content"] == "keep me"

    def test_respects_always_remove_tags(self):
        processor = LastNObservations(
            n=5,
            always_remove_output_for_tags={"remove_output"}
        )
        history: History = [
            create_history_item(content="first", message_type="observation"),
            create_history_item(content="remove me", message_type="observation", tags=["remove_output"]),
            create_history_item(content="last", message_type="observation"),
        ]
        result = processor(history)
        assert "lines omitted" in result[1]["content"]

    def test_ignores_demo_observations(self):
        processor = LastNObservations(n=1)
        history: History = [
            create_history_item(content="first", message_type="observation"),
            create_history_item(content="demo", message_type="observation", is_demo=True),
            create_history_item(content="last", message_type="observation"),
        ]
        result = processor(history)
        assert result[1]["content"] == "demo"

    def test_ignores_non_observation_types(self):
        processor = LastNObservations(n=1)
        history: History = [
            create_history_item(content="first", message_type="observation"),
            create_history_item(content="action", message_type="action"),
            create_history_item(content="last", message_type="observation"),
        ]
        result = processor(history)
        assert result[1]["content"] == "action"

    def test_elided_message_shows_line_count(self):
        processor = LastNObservations(n=1)
        history: History = [
            create_history_item(content="first", message_type="observation"),
            create_history_item(content="line1\nline2\nline3", message_type="observation"),
            create_history_item(content="last", message_type="observation"),
        ]
        result = processor(history)
        assert "3 lines omitted" in result[1]["content"]

    def test_validates_n_positive(self):
        with pytest.raises(ValueError):
            LastNObservations(n=0)
        with pytest.raises(ValueError):
            LastNObservations(n=-1)

    def test_list_content_with_images(self):
        processor = LastNObservations(n=1)
        history: History = [
            create_history_item(content="first", message_type="observation"),
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "line1\nline2"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                ],
                "message_type": "observation",
            },
            create_history_item(content="last", message_type="observation"),
        ]
        result = processor(history)
        assert "2 lines omitted" in result[1]["content"]
        assert "1 images omitted" in result[1]["content"]


class TestTagToolCallObservations:
    def test_adds_tags_to_matching_entries(self):
        processor = TagToolCallObservations(
            tags={"custom_tag"},
            function_names={"edit"}
        )
        history: History = [
            {
                "role": "assistant",
                "content": "editing",
                "message_type": "action",
                "tool_calls": [{"function": {"name": "edit"}}],
            }
        ]
        result = processor(history)
        assert "custom_tag" in result[0]["tags"]

    def test_ignores_non_action_types(self):
        processor = TagToolCallObservations(
            tags={"test"},
            function_names={"edit"}
        )
        history: History = [
            {
                "role": "user",
                "content": "observing",
                "message_type": "observation",
            }
        ]
        result = processor(history)
        assert "tags" not in result[0] or "test" not in result[0].get("tags", [])

    def test_ignores_entries_without_tool_calls(self):
        processor = TagToolCallObservations(
            tags={"test"},
            function_names={"edit"}
        )
        history: History = [
            {
                "role": "assistant",
                "content": "no tools",
                "message_type": "action",
            }
        ]
        result = processor(history)
        assert "tags" not in result[0] or "test" not in result[0].get("tags", [])

    def test_ignores_non_matching_function_names(self):
        processor = TagToolCallObservations(
            tags={"test"},
            function_names={"edit"}
        )
        history: History = [
            {
                "role": "assistant",
                "content": "listing",
                "message_type": "action",
                "tool_calls": [{"function": {"name": "ls"}}],
            }
        ]
        result = processor(history)
        assert "tags" not in result[0] or "test" not in result[0].get("tags", [])

    def test_preserves_existing_tags(self):
        processor = TagToolCallObservations(
            tags={"new_tag"},
            function_names={"edit"}
        )
        history: History = [
            {
                "role": "assistant",
                "content": "editing",
                "message_type": "action",
                "tool_calls": [{"function": {"name": "edit"}}],
                "tags": ["existing_tag"],
            }
        ]
        result = processor(history)
        assert "existing_tag" in result[0]["tags"]
        assert "new_tag" in result[0]["tags"]


class TestCacheControlHistoryProcessor:
    def test_adds_cache_control_to_last_n_messages(self):
        processor = CacheControlHistoryProcessor(last_n_messages=2)
        history: History = [
            create_history_item(role="system", content="system", message_type="system_prompt"),
            create_history_item(role="user", content="user1", message_type="user"),
            create_history_item(role="user", content="user2", message_type="user"),
            create_history_item(role="user", content="user3", message_type="user"),
        ]
        result = processor(history)
        assert "cache_control" not in result[0]
        assert "cache_control" not in result[1]
        assert _has_cache_control(result[2]) or _has_cache_control(result[3])

    def test_removes_cache_control_from_other_messages(self):
        processor = CacheControlHistoryProcessor(last_n_messages=1)
        history: History = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "old", "cache_control": {"type": "ephemeral"}}],
                "message_type": "user",
            },
            create_history_item(role="user", content="new", message_type="user"),
        ]
        result = processor(history)
        assert not _has_cache_control(result[0])

    def test_respects_tagged_roles(self):
        processor = CacheControlHistoryProcessor(
            last_n_messages=2,
            tagged_roles=["user"]
        )
        history: History = [
            create_history_item(role="user", content="user", message_type="user"),
            create_history_item(role="assistant", content="asst", message_type="action"),
            create_history_item(role="user", content="user2", message_type="user"),
        ]
        result = processor(history)
        assert not _has_cache_control(result[1])

    def test_zero_last_n_removes_all(self):
        processor = CacheControlHistoryProcessor(last_n_messages=0)
        history: History = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "test", "cache_control": {"type": "ephemeral"}}],
                "message_type": "user",
            },
        ]
        result = processor(history)
        assert not _has_cache_control(result[0])

    def test_offset_skips_recent_messages(self):
        processor = CacheControlHistoryProcessor(
            last_n_messages=1,
            last_n_messages_offset=1
        )
        history: History = [
            create_history_item(role="user", content="first", message_type="user"),
            create_history_item(role="user", content="second", message_type="user"),
        ]
        result = processor(history)
        assert not _has_cache_control(result[-1])
        assert _has_cache_control(result[-2]) or len(result) < 2


def _has_cache_control(entry: HistoryItem) -> bool:
    """Check if a history item has cache_control set."""
    if "cache_control" in entry:
        return True
    if isinstance(entry.get("content"), list):
        for item in entry["content"]:
            if "cache_control" in item:
                return True
    return False


class TestRemoveRegex:
    def test_removes_matching_patterns(self):
        processor = RemoveRegex(remove=["<diff>.*</diff>"])
        history: History = [
            create_history_item(content="before <diff>removed</diff> after"),
        ]
        result = processor(history)
        assert result[0]["content"] == "before  after"

    def test_respects_keep_last(self):
        processor = RemoveRegex(remove=["secret"], keep_last=1)
        history: History = [
            create_history_item(content="has secret"),
            create_history_item(content="also has secret"),
        ]
        result = processor(history)
        assert "secret" not in result[0]["content"]
        assert "also has secret" in result[1]["content"]

    def test_multiple_patterns(self):
        processor = RemoveRegex(remove=["foo", "bar"])
        history: History = [
            create_history_item(content="foo and bar here"),
        ]
        result = processor(history)
        assert "foo" not in result[0]["content"]
        assert "bar" not in result[0]["content"]

    def test_dotall_flag_for_multiline(self):
        processor = RemoveRegex(remove=["<block>.*</block>"])
        history: History = [
            create_history_item(content="start <block>line1\nline2</block> end"),
        ]
        result = processor(history)
        assert result[0]["content"] == "start  end"

    def test_list_content(self):
        processor = RemoveRegex(remove=["remove_me"])
        history: History = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "keep remove_me keep"}],
                "message_type": "user",
            }
        ]
        result = processor(history)
        assert result[0]["content"][0]["text"] == "keep  keep"

    def test_does_not_modify_original(self):
        processor = RemoveRegex(remove=["remove"])
        history: History = [
            create_history_item(content="remove this"),
        ]
        original_content = history[0]["content"]
        processor(history)
        assert history[0]["content"] == original_content
