"""Tool configuration and handler for the agent.

This module provides configuration and handling of tools that are available
to the agent. It includes:
- Tool filter configuration for blocklisting commands
- Tool configuration for general settings
- Tool handler for validating and processing commands
"""

import re
from functools import cached_property
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from codeagent.commands import Command
from codeagent.parsing import FunctionCallingParser


class ToolFilterConfig(BaseModel):
    """Configuration for filtering/blocking commands.

    Allows specifying commands that should be blocked because they are
    interactive, potentially dangerous, or otherwise unsuitable.
    """

    blocklist_error_template: str = "Operation '{{action}}' is not supported by this environment."

    blocklist: list[str] = [
        "vim",
        "vi",
        "emacs",
        "nano",
        "nohup",
        "gdb",
        "less",
        "tail -f",
        "python -m venv",
        "make",
    ]
    """Block any command that starts with one of these."""

    blocklist_standalone: list[str] = [
        "python",
        "python3",
        "ipython",
        "bash",
        "sh",
        "/bin/bash",
        "/bin/sh",
        "nohup",
        "vi",
        "vim",
        "emacs",
        "nano",
        "su",
    ]
    """Block any command that matches one of these exactly."""

    block_unless_regex: dict[str, str] = {
        "radare2": r"\b(?:radare2)\b.*\s+-c\s+.*",
        "r2": r"\b(?:radare2)\b.*\s+-c\s+.*",
    }
    """Block commands unless they match a specific regex pattern."""


class ToolConfig(BaseModel):
    """Configuration for tools available to the agent.

    Combines filter settings, execution parameters, and environment variables.
    """

    filter: ToolFilterConfig = Field(default_factory=ToolFilterConfig)

    env_variables: dict[str, Any] = {
        "PAGER": "cat",
        "MANPAGER": "cat",
        "LESS": "-R",
        "PIP_PROGRESS_BAR": "off",
        "TQDM_DISABLE": "1",
        "GIT_PAGER": "cat",
    }
    """Environment variables to set for command execution."""

    submit_command: str = "submit"
    """The command used to submit solutions."""

    execution_timeout: int = 30
    """Timeout for executing commands in seconds."""

    total_execution_timeout: int = 1800
    """Total timeout for all command executions."""

    max_consecutive_execution_timeouts: int = 3
    """Maximum consecutive timeouts before stopping."""

    enable_bash_tool: bool = True
    """Whether to enable the bash tool."""

    multi_line_command_endings: dict[str, str] = {}
    """Mapping of command names to their multiline end markers."""

    command_docs: str = ""
    """Documentation for available commands."""

    format_error_template: str = ""
    """Template for format error messages."""

    model_config = ConfigDict(extra="forbid")


class ToolHandler:
    """Handles tool validation and processing for the agent.

    Responsibilities:
    - Validating actions against blocklist
    - Checking for submission commands
    - Generating command documentation
    - Handling multiline command input
    """

    def __init__(self, config: ToolConfig, commands: list[Command] | None = None):
        """Initialize tool handler.

        Args:
            config: Tool configuration
            commands: List of available commands
        """
        self.config = config.model_copy(deep=True)
        self._commands = commands or []
        self._command_patterns = self._build_command_patterns()

    @property
    def commands(self) -> list[Command]:
        """Get the list of available commands."""
        return self._commands

    def add_command(self, command: Command) -> None:
        """Add a command to the handler."""
        self._commands.append(command)
        self._command_patterns = self._build_command_patterns()

    def should_block_action(self, action: str) -> bool:
        """Check if the action should be blocked.

        Args:
            action: The command/action to check

        Returns:
            True if the action should be blocked, False otherwise
        """
        action = action.strip()
        if not action:
            return False

        if any(action.startswith(blocked) for blocked in self.config.filter.blocklist):
            return True

        if action in self.config.filter.blocklist_standalone:
            return True

        first_word = action.split()[0] if action.split() else ""
        if first_word in self.config.filter.block_unless_regex:
            pattern = self.config.filter.block_unless_regex[first_word]
            if not re.search(pattern, action):
                return True

        return False

    def check_for_submission_cmd(self, output: str) -> bool:
        """Check if output indicates a submission command was executed.

        Args:
            output: The command output to check

        Returns:
            True if submission marker found
        """
        return "<<SWE_AGENT_SUBMISSION>>" in output

    def generate_command_docs(self) -> str:
        """Generate documentation for all available commands.

        Returns:
            Formatted documentation string
        """
        docs = []
        for cmd in self._commands:
            doc = f"## {cmd.name}\n"
            if cmd.docstring:
                doc += f"{cmd.docstring}\n"
            if cmd.arguments:
                doc += "Arguments:\n"
                for arg in cmd.arguments:
                    required = " (required)" if arg.required else ""
                    doc += f"  - {arg.name}{required}: {arg.description}\n"
            docs.append(doc)
        return "\n".join(docs)

    def guard_multiline_input(self, action: str) -> str:
        """Handle multiline command input using heredoc syntax.

        Transforms commands that need multiline input into heredoc format
        so they can be properly executed in bash.

        Args:
            action: The action string to process

        Returns:
            Transformed action string with heredoc if needed
        """
        match = self._get_first_multiline_cmd(action)
        if not match:
            return action

        cmd_name = match.group(1)
        cmd_args = match.group(2)

        end_name = None
        for command in self._commands:
            if command.name == cmd_name and command.end_name:
                end_name = command.end_name
                break

        if cmd_name == self.config.submit_command:
            end_name = "END_SUBMIT"

        if end_name is None:
            return action

        before = action[:match.start()]
        after = action[match.end():]

        heredoc = f"{cmd_name} << '{end_name}'\n{cmd_args}\n{end_name}"

        return before + heredoc + after

    def _get_first_multiline_cmd(self, action: str) -> re.Match | None:
        """Find the first multiline command in the action string.

        Returns:
            Match object if found, None otherwise
        """
        matches = []
        for name, pattern in self._command_patterns.items():
            match = pattern.search(action)
            if match:
                matches.append(match)

        if not matches:
            return None

        return min(matches, key=lambda m: m.start())

    def _build_command_patterns(self) -> dict[str, re.Pattern]:
        """Build regex patterns for multiline commands."""
        patterns = {}

        for command in self._commands:
            if command.end_name:
                pattern = re.compile(
                    rf"^\s*({command.name})\s*(.*?)^({command.end_name})\s*$",
                    re.DOTALL | re.MULTILINE,
                )
                patterns[command.name] = pattern

        submit_pattern = re.compile(
            rf"^\s*({self.config.submit_command})\s*(.*?)^(END_SUBMIT)\s*$",
            re.DOTALL | re.MULTILINE,
        )
        patterns[self.config.submit_command] = submit_pattern

        return patterns

    def parse_actions(self, output: dict, parser=None) -> tuple[str, str]:
        """Parse model output into thought and action.

        Args:
            output: Model output dictionary
            parser: Optional parser to use

        Returns:
            Tuple of (thought, action)
        """
        if parser is None:
            parser = FunctionCallingParser()
        return parser(output, self._commands)
