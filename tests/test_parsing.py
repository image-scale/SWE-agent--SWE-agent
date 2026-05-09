"""Tests for LLM output parsers."""

import pytest

from codeagent.commands import Command, CommandArgument
from codeagent.exceptions import FormatError, FunctionCallingFormatError
from codeagent.parsing import (
    ThoughtActionParser,
    XMLThoughtActionParser,
    FunctionCallingParser,
    JsonParser,
    Identity,
    ActionParser,
    ActionOnlyParser,
    EditFormat,
)


class TestThoughtActionParser:
    def test_basic_parsing(self):
        parser = ThoughtActionParser()
        response = {
            "message": "Let's look at the files.\n```\nls -l\n```"
        }
        thought, action = parser(response, [])
        assert thought == "Let's look at the files.\n"
        assert action == "ls -l\n"

    def test_parsing_with_language_tag(self):
        parser = ThoughtActionParser()
        response = {
            "message": "Running bash command:\n```bash\necho hello\n```"
        }
        thought, action = parser(response, [])
        assert "Running bash command" in thought
        assert action == "echo hello\n"

    def test_multiple_code_blocks_uses_last(self):
        parser = ThoughtActionParser()
        response = {
            "message": "First block:\n```\nignored\n```\nSecond:\n```\nused\n```"
        }
        thought, action = parser(response, [])
        assert action == "used\n"

    def test_no_code_block_raises_error(self):
        parser = ThoughtActionParser()
        response = {"message": "No code block here"}
        with pytest.raises(FormatError):
            parser(response, [])

    def test_multiline_action(self):
        parser = ThoughtActionParser()
        response = {
            "message": "Editing file:\n```\nline1\nline2\nline3\n```"
        }
        thought, action = parser(response, [])
        assert "line1\nline2\nline3" in action

    def test_empty_code_block(self):
        parser = ThoughtActionParser()
        response = {"message": "Empty:\n```\n\n```"}
        thought, action = parser(response, [])
        assert action == ""


class TestXMLThoughtActionParser:
    def test_basic_parsing(self):
        parser = XMLThoughtActionParser()
        response = {
            "message": "Let's list files.\n<command>\nls -l\n</command>"
        }
        thought, action = parser(response, [])
        assert thought == "Let's list files."
        assert action == "ls -l"

    def test_missing_command_tags_raises_error(self):
        parser = XMLThoughtActionParser()
        response = {"message": "No command tags here"}
        with pytest.raises(FormatError):
            parser(response, [])

    def test_missing_closing_tag_raises_error(self):
        parser = XMLThoughtActionParser()
        response = {"message": "Opening only <command>ls"}
        with pytest.raises(FormatError):
            parser(response, [])

    def test_whitespace_handling(self):
        parser = XMLThoughtActionParser()
        response = {
            "message": "  Thought  \n<command>\n  action  \n</command>  "
        }
        thought, action = parser(response, [])
        assert action == "action"

    def test_multiple_command_tags_uses_last(self):
        parser = XMLThoughtActionParser()
        response = {
            "message": "<command>first</command><command>second</command>"
        }
        thought, action = parser(response, [])
        assert action == "second"


class TestFunctionCallingParser:
    @pytest.fixture
    def ls_command(self):
        return Command(name="ls", docstring="List files")

    @pytest.fixture
    def grep_command(self):
        return Command(
            name="grep",
            docstring="Search files",
            arguments=[
                CommandArgument(name="pattern", required=True),
                CommandArgument(name="path", required=False),
            ]
        )

    def test_basic_tool_call(self, ls_command):
        parser = FunctionCallingParser()
        response = {
            "message": "Let's list the files",
            "tool_calls": [
                {"function": {"name": "ls", "arguments": "{}"}}
            ]
        }
        thought, action = parser(response, [ls_command])
        assert thought == "Let's list the files"
        assert action == "ls"

    def test_tool_call_with_arguments(self, grep_command):
        parser = FunctionCallingParser()
        response = {
            "message": "Searching",
            "tool_calls": [
                {"function": {"name": "grep", "arguments": '{"pattern": "error", "path": "."}'}}
            ]
        }
        thought, action = parser(response, [grep_command])
        assert thought == "Searching"
        assert "grep" in action
        assert "error" in action

    def test_no_tool_calls_raises_error(self, ls_command):
        parser = FunctionCallingParser()
        response = {"message": "No tools"}
        with pytest.raises(FunctionCallingFormatError) as exc_info:
            parser(response, [ls_command])
        assert exc_info.value.error_code == "missing"
        assert exc_info.value.extra_info["num_tools"] == 0

    def test_multiple_tool_calls_raises_error(self, ls_command):
        parser = FunctionCallingParser()
        response = {
            "message": "Multiple calls",
            "tool_calls": [
                {"function": {"name": "ls", "arguments": "{}"}},
                {"function": {"name": "ls", "arguments": "{}"}},
            ]
        }
        with pytest.raises(FunctionCallingFormatError) as exc_info:
            parser(response, [ls_command])
        assert exc_info.value.error_code == "multiple"
        assert exc_info.value.extra_info["num_tools"] == 2

    def test_unknown_command_raises_error(self, ls_command):
        parser = FunctionCallingParser()
        response = {
            "message": "Unknown",
            "tool_calls": [
                {"function": {"name": "unknown", "arguments": "{}"}}
            ]
        }
        with pytest.raises(FunctionCallingFormatError) as exc_info:
            parser(response, [ls_command])
        assert exc_info.value.error_code == "invalid_command"

    def test_invalid_json_arguments_raises_error(self, ls_command):
        parser = FunctionCallingParser()
        response = {
            "message": "Invalid JSON",
            "tool_calls": [
                {"function": {"name": "ls", "arguments": "not json"}}
            ]
        }
        with pytest.raises(FunctionCallingFormatError) as exc_info:
            parser(response, [ls_command])
        assert exc_info.value.error_code == "invalid_json"

    def test_missing_required_arg_raises_error(self, grep_command):
        parser = FunctionCallingParser()
        response = {
            "message": "Missing pattern",
            "tool_calls": [
                {"function": {"name": "grep", "arguments": '{"path": "."}'}}
            ]
        }
        with pytest.raises(FunctionCallingFormatError) as exc_info:
            parser(response, [grep_command])
        assert exc_info.value.error_code == "missing_arg"

    def test_unexpected_arg_raises_error(self, ls_command):
        parser = FunctionCallingParser()
        response = {
            "message": "Extra args",
            "tool_calls": [
                {"function": {"name": "ls", "arguments": '{"extra": "value"}'}}
            ]
        }
        with pytest.raises(FunctionCallingFormatError) as exc_info:
            parser(response, [ls_command])
        assert exc_info.value.error_code == "unexpected_arg"

    def test_dict_arguments_accepted(self, grep_command):
        parser = FunctionCallingParser()
        response = {
            "message": "Dict args",
            "tool_calls": [
                {"function": {"name": "grep", "arguments": {"pattern": "test"}}}
            ]
        }
        thought, action = parser(response, [grep_command])
        assert "grep" in action
        assert "test" in action

    def test_empty_tool_calls_list_raises_error(self, ls_command):
        parser = FunctionCallingParser()
        response = {
            "message": "Empty list",
            "tool_calls": []
        }
        with pytest.raises(FunctionCallingFormatError) as exc_info:
            parser(response, [ls_command])
        assert exc_info.value.error_code == "missing"


class TestJsonParser:
    def test_basic_parsing(self):
        parser = JsonParser()
        response = {
            "message": '{"thought": "List files", "command": {"name": "ls", "arguments": {}}}'
        }
        thought, action = parser(response, [])
        assert thought == "List files"
        assert action == "ls"

    def test_with_arguments(self):
        parser = JsonParser()
        response = {
            "message": '{"thought": "Search", "command": {"name": "grep", "arguments": {"pattern": "error"}}}'
        }
        thought, action = parser(response, [])
        assert thought == "Search"
        assert "grep" in action
        assert "error" in action

    def test_invalid_json_raises_error(self):
        parser = JsonParser()
        response = {"message": "not json"}
        with pytest.raises(FormatError) as exc_info:
            parser(response, [])
        assert "not valid JSON" in str(exc_info.value)

    def test_missing_thought_raises_error(self):
        parser = JsonParser()
        response = {"message": '{"command": {"name": "ls"}}'}
        with pytest.raises(FormatError) as exc_info:
            parser(response, [])
        assert "thought" in str(exc_info.value)

    def test_missing_command_raises_error(self):
        parser = JsonParser()
        response = {"message": '{"thought": "thinking"}'}
        with pytest.raises(FormatError) as exc_info:
            parser(response, [])
        assert "command" in str(exc_info.value)

    def test_command_not_object_raises_error(self):
        parser = JsonParser()
        response = {"message": '{"thought": "test", "command": "ls"}'}
        with pytest.raises(FormatError) as exc_info:
            parser(response, [])
        assert "not a JSON object" in str(exc_info.value)

    def test_missing_name_raises_error(self):
        parser = JsonParser()
        response = {"message": '{"thought": "test", "command": {"arguments": {}}}'}
        with pytest.raises(FormatError) as exc_info:
            parser(response, [])
        assert "name" in str(exc_info.value)

    def test_not_object_raises_error(self):
        parser = JsonParser()
        response = {"message": '["not", "an", "object"]'}
        with pytest.raises(FormatError) as exc_info:
            parser(response, [])
        assert "not a JSON object" in str(exc_info.value)


class TestIdentity:
    def test_returns_message_unchanged(self):
        parser = Identity()
        response = {"message": "just return this"}
        thought, action = parser(response, [])
        assert thought == "just return this"
        assert action == "just return this"

    def test_multiline_message(self):
        parser = Identity()
        response = {"message": "line1\nline2\nline3"}
        thought, action = parser(response, [])
        assert thought == "line1\nline2\nline3"
        assert action == "line1\nline2\nline3"


class TestActionParser:
    def test_valid_command(self):
        parser = ActionParser()
        ls_cmd = Command(name="ls", docstring="")
        response = {"message": "ls -la"}
        thought, action = parser(response, [ls_cmd])
        assert thought == "ls -la"
        assert action == "ls -la"

    def test_invalid_command_raises_error(self):
        parser = ActionParser()
        ls_cmd = Command(name="ls", docstring="")
        response = {"message": "unknown -flag"}
        with pytest.raises(FormatError):
            parser(response, [ls_cmd])

    def test_empty_message_raises_error(self):
        parser = ActionParser()
        ls_cmd = Command(name="ls", docstring="")
        response = {"message": ""}
        with pytest.raises(FormatError):
            parser(response, [ls_cmd])

    def test_whitespace_only_raises_error(self):
        parser = ActionParser()
        ls_cmd = Command(name="ls", docstring="")
        response = {"message": "   "}
        with pytest.raises(FormatError):
            parser(response, [ls_cmd])


class TestActionOnlyParser:
    def test_returns_empty_thought(self):
        parser = ActionOnlyParser()
        response = {"message": "ls -la"}
        thought, action = parser(response, [])
        assert thought == ""
        assert action == "ls -la"


class TestEditFormat:
    def test_inherits_from_thought_action(self):
        parser = EditFormat()
        response = {"message": "Editing:\n```\nnew content\n```"}
        thought, action = parser(response, [])
        assert action == "new content\n"

    def test_has_edit_specific_error_message(self):
        parser = EditFormat()
        assert "replacement" in parser.error_message.lower()


class TestParserErrorMessages:
    def test_thought_action_has_error_message(self):
        parser = ThoughtActionParser()
        assert parser.error_message != ""
        assert parser.format_error_template == parser.error_message

    def test_function_calling_has_error_message(self):
        parser = FunctionCallingParser()
        assert parser.error_message != ""
        assert "error_code" in parser.error_message

    def test_json_parser_has_error_message(self):
        parser = JsonParser()
        assert parser.error_message != ""
        assert "JSON" in parser.error_message

    def test_xml_parser_has_error_message(self):
        parser = XMLThoughtActionParser()
        assert parser.error_message != ""
        assert "command" in parser.error_message.lower()
