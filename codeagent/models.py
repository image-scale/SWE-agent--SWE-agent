"""Model abstraction layer for language model interactions.

This module provides abstractions for interacting with various language models,
tracking usage statistics, and managing cost limits.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from codeagent.types import History
from codeagent.exceptions import (
    InstanceCostLimitExceededError,
    TotalCostLimitExceededError,
    InstanceCallLimitExceededError,
)


class GlobalStats(BaseModel):
    """Tracks usage statistics across all instances."""

    total_cost: float = 0
    last_query_timestamp: float = 0


GLOBAL_STATS = GlobalStats()


class InstanceStats(BaseModel):
    """Tracks usage statistics for a single problem instance.

    This includes costs, token counts, and API call counts for
    monitoring and enforcing limits.
    """

    instance_cost: float = 0
    tokens_sent: int = 0
    tokens_received: int = 0
    api_calls: int = 0

    def __add__(self, other: "InstanceStats") -> "InstanceStats":
        """Add two InstanceStats together."""
        return InstanceStats(
            instance_cost=self.instance_cost + other.instance_cost,
            tokens_sent=self.tokens_sent + other.tokens_sent,
            tokens_received=self.tokens_received + other.tokens_received,
            api_calls=self.api_calls + other.api_calls,
        )

    def __sub__(self, other: "InstanceStats") -> "InstanceStats":
        """Subtract one InstanceStats from another."""
        return InstanceStats(
            instance_cost=self.instance_cost - other.instance_cost,
            tokens_sent=self.tokens_sent - other.tokens_sent,
            tokens_received=self.tokens_received - other.tokens_received,
            api_calls=self.api_calls - other.api_calls,
        )


class RetryConfig(BaseModel):
    """Configuration for API retry behavior."""

    retries: int = 20
    min_wait: float = 10
    max_wait: float = 120


class ModelConfig(BaseModel):
    """Configuration for language model.

    Provides settings for model selection, sampling parameters,
    and cost/usage limits.
    """

    name: str = Field(description="Name of the model.")
    per_instance_cost_limit: float = Field(
        default=3.0,
        description="Cost limit for each task instance.",
    )
    total_cost_limit: float = Field(
        default=0.0,
        description="Total cost limit across all instances.",
    )
    per_instance_call_limit: int = Field(
        default=0,
        description="Maximum API calls per instance.",
    )
    temperature: float = 0.0
    top_p: float | None = 1.0
    api_base: str | None = None
    api_version: str | None = None
    api_key: SecretStr | None = None
    stop: list[str] = []
    completion_kwargs: dict[str, Any] = {}
    retry: RetryConfig = Field(default_factory=RetryConfig)
    delay: float = 0.0

    model_config = ConfigDict(extra="forbid")

    @property
    def id(self) -> str:
        """Generate a unique identifier for this model configuration."""
        name = self.name.replace("/", "--")
        top_p = f"{self.top_p:.2f}" if self.top_p is not None else "None"
        temperature = f"{self.temperature:.2f}"
        cost_limit = f"{self.per_instance_cost_limit:.2f}"
        return f"{name}__t-{temperature}__p-{top_p}__c-{cost_limit}"


class ReplayModelConfig(ModelConfig):
    """Configuration for replay model."""

    replay_path: Path = Field(description="Path to trajectory file for replay.")
    name: Literal["replay"] = "replay"
    per_instance_cost_limit: float = 0.0
    total_cost_limit: float = 0.0


class AbstractModel(ABC):
    """Abstract base class for all language models.

    Defines the interface that all model implementations must follow.
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self.stats = InstanceStats()

    def reset_stats(self) -> None:
        """Reset statistics for a new instance."""
        self.stats = InstanceStats()

    @abstractmethod
    def query(self, history: History) -> dict:
        """Query the model with conversation history.

        Args:
            history: Conversation history to send to the model

        Returns:
            Dictionary containing at least "message" key with model response
        """
        raise NotImplementedError

    @property
    def instance_cost_limit(self) -> float:
        """Get the cost limit for this instance."""
        return self.config.per_instance_cost_limit


class PredeterminedModel(AbstractModel):
    """Model that returns predetermined responses.

    Useful for testing without making actual API calls.
    """

    def __init__(self, outputs: list[dict | str]):
        """Initialize with a list of predetermined outputs.

        Args:
            outputs: List of responses to return in order.
                    Can be strings or dicts with "message" and optionally "tool_calls".
        """
        self._outputs = outputs
        self._idx = -1
        self.stats = InstanceStats()

    def query(self, history: History) -> dict:
        """Return next predetermined output."""
        self._idx += 1
        output = self._outputs[self._idx]
        self.stats.api_calls += 1

        if isinstance(output, str):
            return {"message": output}
        if isinstance(output, dict):
            result = {"message": output.get("message", "")}
            if "tool_calls" in output:
                result["tool_calls"] = output["tool_calls"]
            return result
        raise ValueError(f"Output must be string or dict, got {type(output)}")


class ReplayModel(AbstractModel):
    """Model that replays actions from a trajectory file.

    Used to re-execute a previously recorded agent run.
    """

    def __init__(self, config: ReplayModelConfig, submit_command: str = "submit"):
        """Initialize replay model.

        Args:
            config: Configuration including path to replay file
            submit_command: Command name used for submission
        """
        self.config = config
        self.stats = InstanceStats()
        self.submit_command = submit_command

        if not self.config.replay_path.exists():
            raise FileNotFoundError(f"Replay file {self.config.replay_path} not found")

        self._replays = [
            list(json.loads(x).values())[0]
            for x in self.config.replay_path.read_text().splitlines(keepends=True)
        ]
        self._replay_idx = 0
        self._action_idx = 0

    def _next_replay(self) -> None:
        """Move to next replay trajectory."""
        self._replay_idx += 1
        self._action_idx = 0

    def query(self, history: History) -> dict:
        """Return next action from replay trajectory."""
        self.stats.api_calls += 1
        actions = self._replays[self._replay_idx]

        try:
            action = actions[self._action_idx]
        except IndexError:
            action = f"```\n{self.submit_command}\n```"

        self._action_idx += 1

        if isinstance(action, str) and action == "submit":
            self._next_replay()
            return {"message": action}

        if isinstance(action, dict):
            return action
        return {"message": action}


class CostTrackingModel(AbstractModel):
    """Model wrapper that tracks costs and enforces limits.

    Can wrap any AbstractModel to add cost tracking and limit enforcement.
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self.stats = InstanceStats()

    def _update_stats(
        self, *, input_tokens: int, output_tokens: int, cost: float
    ) -> None:
        """Update statistics and check cost limits."""
        global GLOBAL_STATS

        GLOBAL_STATS.total_cost += cost
        self.stats.instance_cost += cost
        self.stats.tokens_sent += input_tokens
        self.stats.tokens_received += output_tokens
        self.stats.api_calls += 1

        if 0 < self.config.total_cost_limit < GLOBAL_STATS.total_cost:
            raise TotalCostLimitExceededError("Total cost limit exceeded")

        if 0 < self.config.per_instance_cost_limit < self.stats.instance_cost:
            raise InstanceCostLimitExceededError("Instance cost limit exceeded")

        if 0 < self.config.per_instance_call_limit < self.stats.api_calls:
            raise InstanceCallLimitExceededError("Per instance call limit exceeded")

    def query(self, history: History) -> dict:
        """Query implementation must be provided by subclass."""
        raise NotImplementedError(
            "CostTrackingModel is a base class. Use a concrete implementation."
        )
