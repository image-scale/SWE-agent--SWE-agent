"""Tests for tool configuration and handler."""

import pytest

from codeagent.commands import Command, CommandArgument
from codeagent.tools import (
    ToolFilterConfig,
    ToolConfig,
    ToolHandler,
)


class TestToolFilterConfig:
    def test_default_blocklist(self):
        config = ToolFilterConfig()
        assert "vim" in config.blocklist
        assert "nano" in config.blocklist
        assert "gdb" in config.blocklist

    def test_default_standalone_blocklist(self):
        config = ToolFilterConfig()
        assert "python" in config.blocklist_standalone
        assert "bash" in config.blocklist_standalone

    def test_custom_blocklist(self):
        config = ToolFilterConfig(blocklist=["custom_cmd"])
        assert "custom_cmd" in config.blocklist
        assert "vim" not in config.blocklist


class TestToolConfig:
    def test_default_values(self):
        config = ToolConfig()
        assert config.submit_command == "submit"
        assert config.execution_timeout == 30
        assert config.enable_bash_tool is True
        assert "PAGER" in config.env_variables

    def test_custom_values(self):
        config = ToolConfig(
            submit_command="done",
            execution_timeout=60,
        )
        assert config.submit_command == "done"
        assert config.execution_timeout == 60


class TestToolHandler:
    @pytest.fixture
    def handler(self):
        config = ToolConfig()
        return ToolHandler(config)

    def test_should_block_blocklisted_command(self, handler):
        assert handler.should_block_action("vim file.txt") is True
        assert handler.should_block_action("nano edit.py") is True
        assert handler.should_block_action("gdb ./program") is True

    def test_should_block_standalone_commands(self, handler):
        assert handler.should_block_action("python") is True
        assert handler.should_block_action("bash") is True
        assert handler.should_block_action("python3") is True

    def test_should_not_block_allowed_commands(self, handler):
        assert handler.should_block_action("ls -la") is False
        assert handler.should_block_action("cat file.txt") is False
        assert handler.should_block_action("grep pattern file") is False
        assert handler.should_block_action("python script.py") is False

    def test_empty_action_not_blocked(self, handler):
        assert handler.should_block_action("") is False
        assert handler.should_block_action("   ") is False

    def test_check_for_submission_cmd(self, handler):
        assert handler.check_for_submission_cmd("<<SWE_AGENT_SUBMISSION>>") is True
        assert handler.check_for_submission_cmd("output <<SWE_AGENT_SUBMISSION>> more") is True
        assert handler.check_for_submission_cmd("regular output") is False

    def test_generate_command_docs(self):
        config = ToolConfig()
        commands = [
            Command(
                name="ls",
                docstring="List directory contents",
                arguments=[
                    CommandArgument(name="path", description="Directory path", required=False),
                ],
            ),
            Command(
                name="cat",
                docstring="Display file contents",
                arguments=[
                    CommandArgument(name="file", description="File to display", required=True),
                ],
            ),
        ]
        handler = ToolHandler(config, commands)
        docs = handler.generate_command_docs()

        assert "## ls" in docs
        assert "List directory contents" in docs
        assert "## cat" in docs
        assert "Display file contents" in docs
        assert "path" in docs
        assert "file" in docs
        assert "(required)" in docs

    def test_add_command(self):
        config = ToolConfig()
        handler = ToolHandler(config)
        assert len(handler.commands) == 0

        handler.add_command(Command(name="test", docstring="Test command"))
        assert len(handler.commands) == 1
        assert handler.commands[0].name == "test"

    def test_block_unless_regex(self):
        config = ToolConfig()
        config.filter.block_unless_regex = {"dangerous": r"dangerous\s+--safe"}
        handler = ToolHandler(config)

        assert handler.should_block_action("dangerous") is True
        assert handler.should_block_action("dangerous --safe") is False


class TestToolHandlerMultiline:
    def test_guard_multiline_input_no_match(self):
        config = ToolConfig()
        handler = ToolHandler(config)
        action = "ls -la"
        result = handler.guard_multiline_input(action)
        assert result == action

    def test_guard_multiline_with_end_name(self):
        config = ToolConfig()
        commands = [
            Command(name="edit", docstring="Edit file", end_name="END_EDIT"),
        ]
        handler = ToolHandler(config, commands)

        action = """edit
content here
END_EDIT"""
        result = handler.guard_multiline_input(action)
        assert "<<" in result or result == action

    def test_commands_property(self):
        config = ToolConfig()
        commands = [
            Command(name="cmd1", docstring=""),
            Command(name="cmd2", docstring=""),
        ]
        handler = ToolHandler(config, commands)
        assert len(handler.commands) == 2


class TestToolHandlerParsing:
    def test_parse_actions_with_function_calling(self):
        config = ToolConfig()
        command = Command(name="ls", docstring="")
        handler = ToolHandler(config, [command])

        output = {
            "message": "Let me list files",
            "tool_calls": [{"function": {"name": "ls", "arguments": "{}"}}],
        }
        thought, action = handler.parse_actions(output)
        assert thought == "Let me list files"
        assert action == "ls"


class TestToolConfigIntegration:
    def test_config_to_handler_flow(self):
        filter_config = ToolFilterConfig(
            blocklist=["dangerous"],
            blocklist_standalone=["bad"],
        )
        config = ToolConfig(
            filter=filter_config,
            submit_command="done",
        )
        handler = ToolHandler(config)

        assert handler.should_block_action("dangerous stuff") is True
        assert handler.should_block_action("bad") is True
        assert handler.should_block_action("safe command") is False

    def test_handler_preserves_config(self):
        config = ToolConfig(execution_timeout=120)
        handler = ToolHandler(config)
        assert handler.config.execution_timeout == 120

    def test_handler_copies_config(self):
        config = ToolConfig()
        handler = ToolHandler(config)
        config.execution_timeout = 999
        assert handler.config.execution_timeout == 30
