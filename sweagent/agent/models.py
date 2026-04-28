from __future__ import annotations

from typing import Any

import litellm
from pydantic import BaseModel, SecretStr

from sweagent import __version__
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


class GenericAPIModel(AbstractModel):
    """Model that uses litellm for API completion."""

    def __init__(self, config: GenericAPIModelConfig, tools: ToolConfig):
        self.config = config
        self.tools = tools

    def query(self, history: History) -> dict[str, Any]:
        """Query the model using litellm."""
        # Build completion kwargs
        kwargs = dict(self.config.completion_kwargs)

        # Handle extra_headers - add User-Agent if not already present
        extra_headers = kwargs.get("extra_headers", {})
        if "User-Agent" not in extra_headers:
            extra_headers["User-Agent"] = f"swe-agent/{__version__}"
        kwargs["extra_headers"] = extra_headers

        # Convert history to messages format
        messages = []
        for entry in history:
            messages.append({
                "role": entry.get("role", "user"),
                "content": entry.get("content", ""),
            })

        # Make the API call
        response = litellm.completion(
            model=self.config.name,
            messages=messages,
            api_key=self.config.api_key.get_secret_value() if self.config.api_key else None,
            top_p=self.config.top_p,
            **kwargs,
        )

        # Extract response content
        choice = response.choices[0]
        content = choice.message.content or ""

        result: dict[str, Any] = {"message": content}

        # Include tool calls if present
        if choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                    "id": tc.id,
                }
                for tc in choice.message.tool_calls
            ]

        return result


class InstantEmptySubmitModel(AbstractModel):
    """Model that immediately submits an empty result (for testing)."""

    def __init__(self, tools: ToolConfig):
        self.tools = tools

    def query(self, history: History) -> dict[str, Any]:
        return {"message": ""}


class PredeterminedTestModel(AbstractModel):
    """Test model with predetermined responses."""

    def __init__(self, responses: list[str | dict]):
        self.responses = responses
        self.index = 0

    def query(self, history: History) -> dict[str, Any]:
        if self.index >= len(self.responses):
            return {"message": ""}

        response = self.responses[self.index]
        self.index += 1

        # Handle special test commands
        if isinstance(response, str):
            if response == "raise_cost":
                raise CostLimitExceededError("Cost limit exceeded")
            if response == "raise_context":
                raise ContextLimitExceededError("Context limit exceeded")
            if response == "raise_runtime":
                raise RuntimeError("Runtime error")
            return {"message": response}
        else:
            # It's a dict (e.g., with tool_calls)
            return response


class CostLimitExceededError(Exception):
    """Raised when cost limit is exceeded."""

    pass


class ContextLimitExceededError(Exception):
    """Raised when context limit is exceeded."""

    pass


def get_model(config: ModelConfig, tools: ToolConfig) -> AbstractModel:
    """Factory function to get a model based on configuration."""
    if isinstance(config, GenericAPIModelConfig):
        return GenericAPIModel(config, tools)
    elif isinstance(config, InstantEmptySubmitModelConfig):
        return InstantEmptySubmitModel(tools)
    elif config.name == "instant_empty_submit":
        # Handle case where config is a plain ModelConfig with instant_empty_submit name
        return InstantEmptySubmitModel(tools)
    else:
        # Default to GenericAPIModel for any named model
        api_config = GenericAPIModelConfig(name=config.name)
        return GenericAPIModel(api_config, tools)
