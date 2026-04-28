from __future__ import annotations

import json
import re
from typing import Any

from sweagent.exceptions import FormatError, FunctionCallingFormatError
from sweagent.tools.commands import Command


class ActionParser:
    """Parser that expects raw commands."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        message = model_response.get("message", "")

        # Check if message starts with a valid command name
        valid_command_names = {cmd.name for cmd in commands}

        # Get the first word of the message
        first_word = message.split()[0] if message.split() else ""

        if first_word not in valid_command_names:
            msg = f"Invalid command: {first_word}. Valid commands: {valid_command_names}"
            raise FormatError(msg)

        return (message, message)


class ThoughtActionParser:
    """Parser that expects thought followed by action in code blocks."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        message = model_response.get("message", "")

        # Find code block with triple backticks
        # Pattern: ```[optional language]\n...content...\n```
        pattern = r"```(?:\w*\n)?(.*?)```"
        match = re.search(pattern, message, re.DOTALL)

        if not match:
            msg = "No code block found in response"
            raise FormatError(msg)

        action = match.group(1)
        # Get the thought (everything before the code block)
        thought = message[: match.start()]

        return (thought, action)


class XMLThoughtActionParser:
    """Parser that expects XML-formatted commands."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        message = model_response.get("message", "")

        # Find <command>...</command> tags
        pattern = r"<command>\s*(.*?)\s*</command>"
        match = re.search(pattern, message, re.DOTALL)

        if not match:
            msg = "No <command> tags found in response"
            raise FormatError(msg)

        action = match.group(1).strip()
        # Get the thought (everything before the command tag)
        thought = message[: match.start()].strip()

        return (thought, action)


class EditFormat:
    """Parser for edit commands with code blocks."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        message = model_response.get("message", "")

        # Find code block with triple backticks
        pattern = r"```(?:\w*\n)?(.*?)```"
        match = re.search(pattern, message, re.DOTALL)

        if not match:
            msg = "No code block found in response"
            raise FormatError(msg)

        action = match.group(1)
        # Get the thought (everything before the code block)
        thought = message[: match.start()]

        return (thought, action)


class Identity:
    """Parser that returns input as-is."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        message = model_response.get("message", "")
        return (message, message)


class JsonParser:
    """Parser for JSON-formatted responses."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        message = model_response.get("message", "")

        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON: {e}"
            raise FormatError(msg) from e

        if "thought" not in data or "command" not in data:
            msg = "JSON must contain 'thought' and 'command' keys"
            raise FormatError(msg)

        thought = data["thought"]
        command_data = data["command"]

        # Build the action string from command name and arguments
        action_parts = [command_data["name"]]
        if "arguments" in command_data:
            for value in command_data["arguments"].values():
                action_parts.append(str(value))

        action = " ".join(action_parts)

        return (thought, action)


class FunctionCallingParser:
    """Parser for function calling responses."""

    error_message: str = """
    {% if error_type == 'missing' %}
    The model did not use any tool calls. Please provide a tool call.
    {% else %}
    Error: {{ exception_message }}
    {% endif %}
    """

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        message = model_response.get("message", "")
        tool_calls = model_response.get("tool_calls")

        if not tool_calls:
            raise FunctionCallingFormatError("No tool calls found", "missing")

        if len(tool_calls) > 1:
            msg = "Multiple tool calls not supported"
            raise FormatError(msg)

        tool_call = tool_calls[0]
        function_data = tool_call.get("function", {})
        function_name = function_data.get("name", "")
        arguments_str = function_data.get("arguments", "{}")

        # Validate command exists
        valid_commands = {cmd.name for cmd in commands}
        if function_name not in valid_commands:
            msg = f"Unknown command: {function_name}"
            raise FormatError(msg)

        # Parse arguments
        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in arguments: {e}"
            raise FormatError(msg) from e

        # Build the action string
        action_parts = [function_name]
        for value in arguments.values():
            action_parts.append(str(value))

        action = " ".join(action_parts)

        return (message, action)
