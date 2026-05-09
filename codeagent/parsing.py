"""Parsers for extracting thought and action from LLM responses.

This module provides various parsing strategies for interpreting language model
output and extracting the thought (reasoning) and action (command to execute)
components.

Parsers handle different output formats:
- ThoughtActionParser: Backtick-wrapped code blocks
- XMLThoughtActionParser: XML <command></command> tags
- FunctionCallingParser: LiteLLM tool calls
- JsonParser: JSON objects with thought and command fields
- Identity: No parsing, returns message as-is
"""

import json
import re
from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

from codeagent.exceptions import FormatError, FunctionCallingFormatError
from codeagent.commands import Command


class AbstractParser(ABC):
    """Base class for all parsers."""

    error_message: str = ""

    @abstractmethod
    def __call__(self, model_response: dict, commands: list[Command]) -> tuple[str, str]:
        """Parse model response into thought and action.

        Args:
            model_response: Dictionary containing at least "message" key
            commands: List of available commands

        Returns:
            Tuple of (thought, action) strings

        Raises:
            FormatError: If response cannot be parsed
        """
        raise NotImplementedError

    @property
    def format_error_template(self) -> str:
        """Template for error messages shown to the model."""
        return self.error_message


class ThoughtActionParser(AbstractParser, BaseModel):
    """Parses responses with discussion followed by backtick-wrapped code blocks.

    Expected format:
        Let's look at the files in the current directory.
        ```
        ls -l
        ```
    """

    error_message: str = """Your output was not formatted correctly. You must always include one discussion and one command as part of your response.
Please make sure your output precisely matches the following format:
DISCUSSION
Discuss here with yourself about what your planning and what you're going to do in this step.

```
command(s) that you're going to run
```
"""

    type: Literal["thought_action"] = "thought_action"

    def __call__(self, model_response: dict, commands: list[Command]) -> tuple[str, str]:
        """Parse thought and action from backtick code blocks.

        Finds the last non-nested code block and extracts its content as the action.
        Everything else is treated as the thought.
        """
        message = model_response["message"]
        code_block_pat = re.compile(r"^```(\S*)\s*\n|^```\s*$", re.MULTILINE)
        stack = []
        last_valid_block = None

        for match in code_block_pat.finditer(message):
            if stack and not match.group(1):
                start = stack.pop()
                if not stack:
                    last_valid_block = (start, match)
            elif match.group(1) is not None:
                stack.append(match)

        if last_valid_block:
            start, end = last_valid_block
            thought = message[:start.start()] + message[end.end():]
            action = message[start.end():end.start()]
            return thought, action

        raise FormatError("No action found in model response.")


class XMLThoughtActionParser(AbstractParser, BaseModel):
    """Parses responses with XML command tags.

    Expected format:
        Let's look at the files.
        <command>
        ls -l
        </command>
    """

    error_message: str = """Your output was not formatted correctly. You must always include one discussion and one command.
Please make sure your output precisely matches the following format with <command></command> tags:

DISCUSSION
Your reasoning here.

<command>
command to run
</command>
"""

    type: Literal["xml_thought_action"] = "xml_thought_action"

    def __call__(self, model_response: dict, commands: list[Command]) -> tuple[str, str]:
        """Parse thought and action from XML command tags."""
        message = model_response["message"]

        if "<command>" not in message or "</command>" not in message:
            raise FormatError("No action found in model response.")

        start_action = message.rfind("<command>") + len("<command>")
        end_thought = message.rfind("<command>")
        end_action = message.rfind("</command>")
        restart_thought = message.rfind("</command>") + len("</command>")

        action = message[start_action:end_action]
        thought = message[:end_thought] + message[restart_thought:]

        return thought.strip(), action.strip()


class FunctionCallingParser(AbstractParser, BaseModel):
    """Parses responses using LiteLLM tool/function calls.

    Expects model_response to contain a "tool_calls" list with exactly one tool call.
    """

    error_message: str = """{%- if error_code == "missing" -%}
Your last output did not use any tool calls!
Please make sure your output includes exactly ONE function call.
You must invoke the function directly using the function call format.
{%- elif error_code == "multiple" -%}
Your last output included multiple tool calls!
Please make sure your output includes exactly ONE function call.
{%- elif error_code == "unexpected_arg" -%}
Your action could not be parsed: {{exception_message}}.
Make sure your function call only uses allowed arguments.
{%- else -%}
Your action could not be parsed: {{exception_message}}.
{% endif %}
"""

    type: Literal["function_calling"] = "function_calling"

    def _parse_tool_call(self, tool_call: dict, commands: list[Command]) -> str:
        """Parse a single tool call into an action string."""
        name = tool_call["function"]["name"]
        command_map = {c.name: c for c in commands}
        command = command_map.get(name)

        if not command:
            raise FunctionCallingFormatError(
                f"Command '{name}' not found in available commands.",
                "invalid_command"
            )

        args_data = tool_call["function"]["arguments"]
        if isinstance(args_data, str):
            try:
                values = json.loads(args_data)
            except json.JSONDecodeError:
                raise FunctionCallingFormatError(
                    "Tool call arguments are not valid JSON.",
                    "invalid_json"
                )
        else:
            values = args_data

        required_args = {arg.name for arg in command.arguments if arg.required}
        missing_args = required_args - set(values.keys())
        if missing_args:
            raise FunctionCallingFormatError(
                f"Required argument(s) missing: {', '.join(missing_args)}",
                "missing_arg"
            )

        valid_args = {arg.name for arg in command.arguments}
        extra_args = set(values.keys()) - valid_args
        if command.end_name:
            extra_args.discard(command.end_name)
        if extra_args:
            raise FunctionCallingFormatError(
                f"Unexpected argument(s): {', '.join(extra_args)}",
                "unexpected_arg"
            )

        parts = [name]
        for arg in command.arguments:
            if arg.name in values:
                parts.append(str(values[arg.name]))

        return " ".join(parts)

    def __call__(self, model_response: dict, commands: list[Command]) -> tuple[str, str]:
        """Parse tool calls from model response."""
        message = model_response.get("message", "")
        tool_calls = model_response.get("tool_calls")

        if not tool_calls:
            raise FunctionCallingFormatError(
                f"Expected tool call in model response, received none with message: {message}",
                "missing",
                num_tools=0
            )

        if len(tool_calls) > 1:
            raise FunctionCallingFormatError(
                f"Expected exactly one tool call, received {len(tool_calls)}",
                "multiple",
                num_tools=len(tool_calls)
            )

        action = self._parse_tool_call(tool_calls[0], commands)
        return message, action


class JsonParser(AbstractParser, BaseModel):
    """Parses JSON-formatted responses.

    Expected format:
        {
            "thought": "I should list the files",
            "command": {
                "name": "ls",
                "arguments": {"path": "."}
            }
        }
    """

    error_message: str = """Your output could not be parsed as JSON. Please make sure your output:
1) Is valid JSON
2) Includes the "thought" and "command" fields

Example format:
{
    "thought": "Your reasoning here",
    "command": {
        "name": "command_name",
        "arguments": {}
    }
}
"""

    type: Literal["json"] = "json"

    def __call__(self, model_response: dict, commands: list[Command]) -> tuple[str, str]:
        """Parse JSON response into thought and action."""
        message = model_response["message"]

        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            raise FormatError("Model output is not valid JSON.")

        if not isinstance(data, dict):
            raise FormatError("Model output is not a JSON object.")

        if "thought" not in data:
            raise FormatError("Key 'thought' is missing from model output.")

        if "command" not in data:
            raise FormatError("Key 'command' is missing from model output.")

        command_data = data["command"]
        if not isinstance(command_data, dict):
            raise FormatError("Value of 'command' key is not a JSON object.")

        if "name" not in command_data:
            raise FormatError("Key 'name' is missing from 'command' object.")

        thought = data["thought"]
        cmd_name = command_data["name"]
        args = command_data.get("arguments", {})

        parts = [cmd_name]
        for value in args.values():
            parts.append(str(value))

        return thought, " ".join(parts)


class Identity(AbstractParser, BaseModel):
    """No-op parser that returns the message unchanged.

    Useful when the model output is already in the correct format
    or when no parsing is needed.
    """

    error_message: str = "Something went wrong with your output. Please try again."

    type: Literal["identity"] = "identity"

    def __call__(self, model_response: dict, commands: list[Command]) -> tuple[str, str]:
        """Return message as both thought and action."""
        message = model_response["message"]
        return message, message


class ActionParser(AbstractParser, BaseModel):
    """Parses responses that are just a single command.

    Verifies that the first word of the response is a known command.
    """

    error_message: str = """The command you provided was not recognized. Please specify one of the available commands.
"""

    type: Literal["action"] = "action"

    def __call__(self, model_response: dict, commands: list[Command]) -> tuple[str, str]:
        """Parse action-only response."""
        message = model_response["message"]
        words = message.strip().split()

        if words:
            first_word = words[0]
            command_names = {c.name for c in commands}
            if first_word in command_names:
                return message, message

        raise FormatError("First word in model response is not a valid command.")


class ActionOnlyParser(AbstractParser, BaseModel):
    """Simple parser that treats the entire message as an action.

    Does not validate against command list.
    """

    error_message: str = "No message found in model response."

    type: Literal["action_only"] = "action_only"

    def __call__(self, model_response: dict, commands: list[Command]) -> tuple[str, str]:
        """Return message as action with empty thought."""
        message = model_response["message"]
        return "", message


class EditFormat(ThoughtActionParser):
    """Variant of ThoughtActionParser for edit operations.

    Same parsing logic but with a different error message template
    focused on edit/replace operations.
    """

    error_message: str = """Your output was not formatted correctly. You must wrap the replacement text in backticks (```).
Please make sure your output precisely matches the following format:

COMMENTS
Your comments about the changes.

```
New content here.
```
"""

    type: Literal["edit_format"] = "edit_format"
