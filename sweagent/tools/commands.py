from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel


class Argument(BaseModel):
    """Represents a command argument."""

    name: str
    type: str
    description: str
    required: bool = True
    enum: list[str] | None = None
    argument_format: str | None = None


class Command(BaseModel):
    """Represents a tool command."""

    name: str
    docstring: str
    signature: str | None = None
    arguments: list[Argument] = []
    end_name: str | None = None
    _invoke_format: str | None = None

    class Config:
        underscore_attrs_are_private = True

    def model_post_init(self, __context: Any) -> None:
        """Validate and process the command after initialization."""
        self._validate_arguments()
        self._build_invoke_format()

    def _validate_arguments(self) -> None:
        """Validate argument names and ordering."""
        # Check for valid argument names
        for arg in self.arguments:
            # Valid names: start with letter or underscore, followed by alphanumeric/underscore/dash
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_-]*$", arg.name):
                msg = f"Invalid argument name: '{arg.name}'"
                raise ValueError(msg)

        # Check for duplicate argument names
        names = [arg.name for arg in self.arguments]
        if len(names) != len(set(names)):
            msg = "Duplicate argument names found"
            raise ValueError(msg)

        # Check that required arguments come before optional ones
        seen_optional = False
        for arg in self.arguments:
            if not arg.required:
                seen_optional = True
            elif seen_optional:
                msg = f"Required argument '{arg.name}' cannot come after optional arguments"
                raise ValueError(msg)

        # If signature provided, validate consistency
        if self.signature:
            self._validate_signature_consistency()

    def _validate_signature_consistency(self) -> None:
        """Validate that signature and arguments are consistent."""
        if not self.signature:
            return

        # Extract argument names from signature using <name> or [<name>] pattern
        signature_args = re.findall(r"<(\w+)>", self.signature)
        argument_names = [arg.name for arg in self.arguments]

        # Check all defined arguments are in signature
        for arg_name in argument_names:
            if arg_name not in signature_args:
                msg = f"Missing argument '{arg_name}' in signature"
                raise ValueError(msg)

        # Check signature arguments match defined arguments
        if set(signature_args) != set(argument_names):
            msg = f"Argument names {argument_names} do not match signature arguments {signature_args}"
            raise ValueError(msg)

    def _build_invoke_format(self) -> None:
        """Build the invoke format string."""
        if self.signature:
            # Use signature as base, replace <name> with {name} and strip [...] brackets
            format_str = self.signature
            # Replace <name> with {name}
            format_str = re.sub(r"<(\w+)>", r"{\1}", format_str)
            # Remove [...] optional brackets but keep content
            format_str = re.sub(r"\[([^\]]+)\]", r"\1", format_str)
            self._invoke_format = format_str
        else:
            # Build default format: name {arg1} {arg2} ...
            parts = [self.name]
            for arg in self.arguments:
                parts.append("{" + arg.name + "}")
            self._invoke_format = " ".join(parts) + " "

    @property
    def invoke_format(self) -> str:
        """Get the invoke format string."""
        if self._invoke_format is None:
            self._build_invoke_format()
        return self._invoke_format or self.name

    def get_function_calling_tool(self) -> dict[str, Any]:
        """Generate OpenAI function calling tool definition."""
        properties = {}
        required = []

        for arg in self.arguments:
            prop: dict[str, Any] = {
                "type": arg.type,
                "description": arg.description,
            }
            if arg.enum:
                prop["enum"] = arg.enum

            properties[arg.name] = prop

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
