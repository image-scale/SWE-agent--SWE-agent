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
        # Convert parse_function dict to actual parser instance
        if isinstance(self.parse_function, dict):
            parser_type = self.parse_function.get("type", "identity")
            self.parse_function = _get_parser_by_type(parser_type)
        elif self.parse_function is None:
            # Default to Identity parser
            from sweagent.tools.parsing import Identity
            self.parse_function = Identity()


def _get_parser_by_type(parser_type: str) -> Any:
    """Get a parser instance by type name."""
    from sweagent.tools.parsing import (
        Identity,
        ThoughtActionParser,
        XMLThoughtActionParser,
        FunctionCallingParser,
        ActionParser,
        JsonParser,
        EditFormat,
    )

    parsers = {
        "identity": Identity,
        "thought_action": ThoughtActionParser,
        "xml_thought_action": XMLThoughtActionParser,
        "function_calling": FunctionCallingParser,
        "action": ActionParser,
        "json": JsonParser,
        "edit_format": EditFormat,
    }

    parser_cls = parsers.get(parser_type, Identity)
    return parser_cls()
