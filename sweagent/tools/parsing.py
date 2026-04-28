from __future__ import annotations

from typing import Any

from sweagent.tools.commands import Command


class ActionParser:
    """Parser that expects raw commands."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        raise NotImplementedError


class ThoughtActionParser:
    """Parser that expects thought followed by action in code blocks."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        raise NotImplementedError


class XMLThoughtActionParser:
    """Parser that expects XML-formatted commands."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        raise NotImplementedError


class EditFormat:
    """Parser for edit commands with code blocks."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        raise NotImplementedError


class Identity:
    """Parser that returns input as-is."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        raise NotImplementedError


class JsonParser:
    """Parser for JSON-formatted responses."""

    def __call__(self, model_response: dict[str, Any], commands: list[Command]) -> tuple[str, str]:
        raise NotImplementedError


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
        raise NotImplementedError
