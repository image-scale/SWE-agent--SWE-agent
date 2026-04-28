from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sweagent.tools.commands import Command


class Bundle(BaseModel):
    """Represents a bundle of tools."""

    path: Path
    hidden_tools: list[str] = []


class ToolConfig(BaseModel):
    """Configuration for tools."""

    parse_function: Any = None
    bundles: list[Bundle] = []
    env_variables: dict[str, Any] = {}
    commands: list[Command] = []
    mock_state: dict[str, Any] = {}

    def model_post_init(self, __context: Any) -> None:
        pass
