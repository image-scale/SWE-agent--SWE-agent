"""Tests for core types and exceptions."""

import pytest
from codeagent.types import (
    StepOutput,
    TrajectoryStep,
    HistoryItem,
    History,
    Trajectory,
    AgentInfo,
    AgentRunResult,
)
from codeagent.exceptions import (
    FormatError,
    FunctionCallingFormatError,
    ContextWindowExceededError,
    CostLimitExceededError,
    InstanceCostLimitExceededError,
    TotalCostLimitExceededError,
    InstanceCallLimitExceededError,
    ContentPolicyViolationError,
    ModelConfigurationError,
)


class TestStepOutput:
    def test_default_values(self):
        step = StepOutput()
        assert step.thought == ""
        assert step.action == ""
        assert step.output == ""
        assert step.observation == ""
        assert step.execution_time == 0.0
        assert step.done is False
        assert step.exit_status is None
        assert step.submission is None
        assert step.state == {}
        assert step.tool_calls is None
        assert step.tool_call_ids is None
        assert step.extra_info == {}

    def test_custom_values(self):
        step = StepOutput(
            thought="Let me check the files",
            action="ls -la",
            observation="file1.py file2.py",
            execution_time=1.5,
            done=True,
            exit_status="submitted",
            submission="diff --git a/file.py",
            state={"cwd": "/repo"},
        )
        assert step.thought == "Let me check the files"
        assert step.action == "ls -la"
        assert step.observation == "file1.py file2.py"
        assert step.execution_time == 1.5
        assert step.done is True
        assert step.exit_status == "submitted"
        assert step.submission == "diff --git a/file.py"
        assert step.state == {"cwd": "/repo"}

    def test_to_template_format_dict_excludes_complex_types(self):
        step = StepOutput(
            thought="thinking",
            action="do something",
            tool_calls=[{"function": {"name": "test"}}],
            tool_call_ids=["call_123"],
            state={"cwd": "/home"},
        )
        result = step.to_template_format_dict()
        assert "tool_calls" not in result
        assert "tool_call_ids" not in result
        assert "state" not in result

    def test_to_template_format_dict_flattens_state(self):
        step = StepOutput(
            thought="thinking",
            action="do something",
            state={"cwd": "/home", "file": "test.py"},
        )
        result = step.to_template_format_dict()
        assert result["cwd"] == "/home"
        assert result["file"] == "test.py"
        assert result["thought"] == "thinking"
        assert result["action"] == "do something"

    def test_to_template_format_dict_returns_correct_types(self):
        step = StepOutput(
            execution_time=2.5,
            done=True,
            exit_status="success",
        )
        result = step.to_template_format_dict()
        assert isinstance(result["execution_time"], float)
        assert isinstance(result["done"], bool)
        assert isinstance(result["exit_status"], str)


class TestTrajectoryStep:
    def test_trajectory_step_structure(self):
        step: TrajectoryStep = {
            "action": "ls -la",
            "observation": "file1.py",
            "response": "Let me list files",
            "state": {"cwd": "/repo"},
            "thought": "I should check the directory",
            "execution_time": 0.5,
            "query": [{"role": "user", "content": "Fix the bug"}],
            "extra_info": {"attempts": 1},
        }
        assert step["action"] == "ls -la"
        assert step["observation"] == "file1.py"
        assert step["response"] == "Let me list files"
        assert step["state"]["cwd"] == "/repo"
        assert step["thought"] == "I should check the directory"
        assert step["execution_time"] == 0.5
        assert len(step["query"]) == 1
        assert step["extra_info"]["attempts"] == 1


class TestHistoryItem:
    def test_required_fields(self):
        item: HistoryItem = {
            "role": "assistant",
            "content": "I'll help you fix the bug",
            "message_type": "action",
        }
        assert item["role"] == "assistant"
        assert item["content"] == "I'll help you fix the bug"
        assert item["message_type"] == "action"

    def test_optional_fields(self):
        item: HistoryItem = {
            "role": "assistant",
            "content": "Let me check",
            "message_type": "observation",
            "agent": "main",
            "is_demo": True,
            "thought": "I need to investigate",
            "action": "grep -r bug",
            "tool_calls": [{"function": "bash"}],
            "tool_call_ids": ["call_1"],
            "tags": ["important"],
        }
        assert item["agent"] == "main"
        assert item["is_demo"] is True
        assert item["thought"] == "I need to investigate"
        assert item["action"] == "grep -r bug"
        assert len(item["tool_calls"]) == 1
        assert item["tool_call_ids"][0] == "call_1"
        assert "important" in item["tags"]

    def test_list_content(self):
        item: HistoryItem = {
            "role": "user",
            "content": [{"type": "text", "text": "Hello"}],
            "message_type": "user",
        }
        assert isinstance(item["content"], list)
        assert item["content"][0]["text"] == "Hello"


class TestHistoryAndTrajectory:
    def test_history_is_list_of_items(self):
        history: History = [
            {"role": "system", "content": "You are an agent", "message_type": "system_prompt"},
            {"role": "user", "content": "Fix this bug", "message_type": "user"},
            {"role": "assistant", "content": "I'll help", "message_type": "action"},
        ]
        assert len(history) == 3
        assert history[0]["role"] == "system"
        assert history[2]["message_type"] == "action"

    def test_trajectory_is_list_of_steps(self):
        trajectory: Trajectory = [
            {
                "action": "ls",
                "observation": "files",
                "response": "checking",
                "state": {},
                "thought": "thinking",
                "execution_time": 0.1,
                "query": [],
                "extra_info": {},
            },
            {
                "action": "cat file.py",
                "observation": "code here",
                "response": "reading",
                "state": {},
                "thought": "reviewing",
                "execution_time": 0.2,
                "query": [],
                "extra_info": {},
            },
        ]
        assert len(trajectory) == 2
        assert trajectory[0]["action"] == "ls"
        assert trajectory[1]["action"] == "cat file.py"


class TestAgentInfo:
    def test_all_optional_fields(self):
        info: AgentInfo = {}
        assert len(info) == 0

    def test_partial_fields(self):
        info: AgentInfo = {
            "exit_status": "submitted",
            "submission": "diff --git",
            "model_stats": {"tokens_sent": 100, "cost": 0.05},
        }
        assert info["exit_status"] == "submitted"
        assert info["submission"] == "diff --git"
        assert info["model_stats"]["tokens_sent"] == 100


class TestAgentRunResult:
    def test_create_result(self):
        result = AgentRunResult(
            info={"exit_status": "success", "submission": "patch"},
            trajectory=[
                {
                    "action": "ls",
                    "observation": "output",
                    "response": "resp",
                    "state": {},
                    "thought": "think",
                    "execution_time": 0.1,
                    "query": [],
                    "extra_info": {},
                }
            ],
        )
        assert result.info["exit_status"] == "success"
        assert len(result.trajectory) == 1
        assert result.trajectory[0]["action"] == "ls"


class TestFormatError:
    def test_basic_exception(self):
        with pytest.raises(FormatError):
            raise FormatError("Could not parse response")

    def test_exception_message(self):
        error = FormatError("Invalid format: missing code block")
        assert "Invalid format" in str(error)


class TestFunctionCallingFormatError:
    def test_with_error_code(self):
        error = FunctionCallingFormatError("No tool calls", "missing")
        assert error.message == "No tool calls"
        assert error.error_code == "missing"
        assert error.extra_info["error_code"] == "missing"
        assert "[error_code=missing]" in str(error)

    def test_with_extra_info(self):
        error = FunctionCallingFormatError(
            "Too many tools", "multiple", num_tools=3
        )
        assert error.extra_info["num_tools"] == 3
        assert error.extra_info["error_code"] == "multiple"

    def test_inherits_from_format_error(self):
        error = FunctionCallingFormatError("test", "invalid_json")
        assert isinstance(error, FormatError)

    def test_different_error_codes(self):
        codes = ["missing", "multiple", "incorrect_args", "invalid_json",
                 "invalid_command", "missing_arg", "unexpected_arg"]
        for code in codes:
            error = FunctionCallingFormatError("test", code)
            assert error.error_code == code


class TestContextWindowExceededError:
    def test_basic_exception(self):
        with pytest.raises(ContextWindowExceededError):
            raise ContextWindowExceededError("Input tokens exceed max")

    def test_exception_message(self):
        error = ContextWindowExceededError("128000 tokens > 100000 max")
        assert "128000 tokens" in str(error)


class TestCostLimitErrors:
    def test_base_cost_limit_error(self):
        with pytest.raises(CostLimitExceededError):
            raise CostLimitExceededError("Cost limit hit")

    def test_instance_cost_limit(self):
        error = InstanceCostLimitExceededError("$3.50 > $3.00 limit")
        assert isinstance(error, CostLimitExceededError)
        assert "$3.50" in str(error)

    def test_total_cost_limit(self):
        error = TotalCostLimitExceededError("Total exceeded $100")
        assert isinstance(error, CostLimitExceededError)
        assert "Total exceeded" in str(error)

    def test_call_limit(self):
        error = InstanceCallLimitExceededError("50 calls > 40 limit")
        assert isinstance(error, CostLimitExceededError)
        assert "50 calls" in str(error)


class TestContentPolicyViolationError:
    def test_basic_exception(self):
        with pytest.raises(ContentPolicyViolationError):
            raise ContentPolicyViolationError("Content blocked")


class TestModelConfigurationError:
    def test_basic_exception(self):
        with pytest.raises(ModelConfigurationError):
            raise ModelConfigurationError("Invalid model name")

    def test_exception_message(self):
        error = ModelConfigurationError("API key missing for model X")
        assert "API key missing" in str(error)
