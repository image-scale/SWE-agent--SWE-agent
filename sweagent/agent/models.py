from __future__ import annotations

from typing import Any

from pydantic import BaseModel, SecretStr

from sweagent.tools.tools import ToolConfig
from sweagent.types import History


class ModelConfig(BaseModel):
    """Base configuration for models."""

    name: str = ""


class GenericAPIModelConfig(ModelConfig):
    """Configuration for generic API models."""

    name: str = "gpt-4o"
    api_key: SecretStr | None = None
    top_p: float | None = 0.95
    completion_kwargs: dict[str, Any] = {}
    per_instance_cost_limit: float = 3.0
    total_cost_limit: float = 10.0


class InstantEmptySubmitModelConfig(ModelConfig):
    """Configuration for instant empty submit model (for testing)."""

    name: str = "instant_empty_submit"


class AbstractModel:
    """Base class for models."""

    def query(self, history: History) -> dict[str, Any]:
        raise NotImplementedError


class PredeterminedTestModel(AbstractModel):
    """Test model with predetermined responses."""

    def __init__(self, responses: list[str | dict]):
        self.responses = responses
        self.index = 0

    def query(self, history: History) -> dict[str, Any]:
        raise NotImplementedError


def get_model(config: ModelConfig, tools: ToolConfig) -> AbstractModel:
    """Factory function to get a model based on configuration."""
    raise NotImplementedError
