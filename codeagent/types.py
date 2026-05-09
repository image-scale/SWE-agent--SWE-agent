"""Core data types used throughout the agent system.

This module defines the primary data structures exchanged between different
components of the agent, including step outputs, trajectory steps, and
history items.
"""

from typing import Any, Literal

from pydantic import BaseModel
from typing_extensions import TypedDict


class StepOutput(BaseModel):
    """Represents the output of a single agent step.

    This includes the model's thought process, the action taken,
    observations from the environment, and various metadata.
    """
    query: list[dict] = [{}]
    thought: str = ""
    action: str = ""
    output: str = ""
    observation: str = ""
    execution_time: float = 0.0
    done: bool = False
    exit_status: int | str | None = None
    submission: str | None = None
    state: dict[str, str] = {}
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_ids: list[str] | None = None
    thinking_blocks: list[dict[str, Any]] | None = None
    extra_info: dict[str, Any] = {}

    def to_template_format_dict(self) -> dict[str, str | int | float | bool | None]:
        """Convert step output to a dictionary suitable for template rendering.

        Excludes complex nested types that can't be easily rendered in templates
        and flattens the state dictionary into the output.
        """
        result = {}
        for key, value in self.model_dump().items():
            if key in ("tool_calls", "tool_call_ids", "state"):
                continue
            result[key] = value
        result.update(self.state)
        return result


class TrajectoryStep(TypedDict):
    """A single step in the agent's trajectory.

    Records what action was taken, what was observed, and the state
    of the environment at that point.
    """
    action: str
    observation: str
    response: str
    state: dict[str, str]
    thought: str
    execution_time: float
    query: list[dict[str, Any]]
    extra_info: dict[str, Any]


class _HistoryItemRequired(TypedDict):
    """Required fields for a history item."""
    role: str
    content: str | list[dict[str, Any]]
    message_type: Literal["thought", "action", "observation", "system_prompt", "demonstration", "user", "assistant"]


class HistoryItem(_HistoryItemRequired, total=False):
    """An item in the conversation history.

    Contains the message content along with metadata about its origin
    and any associated tool calls.
    """
    agent: str
    is_demo: bool
    thought: str
    action: str | None
    tool_calls: list[dict[str, str]] | None
    tool_call_ids: list[str] | None
    tags: list[str]
    cache_control: dict[str, Any] | None
    thinking_blocks: list[dict[str, Any]] | None


History = list[HistoryItem]
Trajectory = list[TrajectoryStep]


class AgentInfo(TypedDict, total=False):
    """Information about an agent's run on a problem instance.

    Contains statistics about model usage, the final submission,
    and various metadata about the run.
    """
    model_stats: dict[str, float]
    exit_status: str | None
    submission: str | None
    review: dict[str, Any]
    edited_files30: str
    edited_files50: str
    edited_files70: str
    summarizer: dict
    agent_hash: str
    agent_version: str


class AgentRunResult(BaseModel):
    """The result of running an agent on a problem instance.

    Contains the collected information about the run and the full
    trajectory of steps taken.
    """
    info: AgentInfo
    trajectory: Trajectory
