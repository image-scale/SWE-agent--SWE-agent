"""Command definitions for tools.

This module defines the Command class which represents a tool that can be
invoked by the agent.
"""

from typing import Any
from pydantic import BaseModel


class CommandArgument(BaseModel):
    """An argument for a command."""
    name: str
    description: str = ""
    required: bool = False
    argument_format: str = "{{value}}"


class Command(BaseModel):
    """Represents a command/tool that can be invoked by the agent.

    Commands are the tools available to the agent for interacting with
    the environment.
    """
    name: str
    docstring: str = ""
    arguments: list[CommandArgument] = []
    end_name: str | None = None
    invoke_format: str = "{name}"

    def get_function_calling_tool(self) -> dict[str, Any]:
        """Convert command to function calling tool format."""
        properties = {}
        required = []
        for arg in self.arguments:
            properties[arg.name] = {
                "type": "string",
                "description": arg.description,
            }
            if arg.required:
                required.append(arg.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.docstring,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
