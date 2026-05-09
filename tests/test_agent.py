"""Tests for the agent module."""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from codeagent.agent import (
    AgentConfig,
    DefaultAgent,
    AgentHook,
    CombinedAgentHook,
    TemplateConfig,
)
from codeagent.commands import Command
from codeagent.history import DefaultHistoryProcessor
from codeagent.models import InstanceStats
from codeagent.problem import TextProblemStatement
from codeagent.tools import ToolConfig, ToolHandler
from codeagent.types import StepOutput


class MockModel:
    """Mock model for testing."""

    def __init__(self, responses: list[str | dict] | None = None):
        self.responses = responses or [
            {
                "message": "Let me list the files",
                "tool_calls": [{"function": {"name": "ls", "arguments": "{}"}}],
            }
        ]
        self._idx = 0
        self.stats = InstanceStats()
        self.queries: list[list[dict]] = []

    def query(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        self.queries.append(messages)
        if self._idx < len(self.responses):
            response = self.responses[self._idx]
            self._idx += 1
        else:
            response = self.responses[-1]
        if isinstance(response, str):
            return {
                "message": response,
                "tool_calls": [{"function": {"name": "echo", "arguments": "{}"}}],
            }
        return response


class MockEnvironment:
    """Mock environment for testing."""

    def __init__(self, outputs: list[str] | None = None):
        self.outputs = outputs or ["file1.txt\nfile2.txt"]
        self._idx = 0
        self.commands: list[str] = []
        self.repo = None

    def communicate(self, command: str) -> str:
        self.commands.append(command)
        if self._idx < len(self.outputs):
            output = self.outputs[self._idx]
            self._idx += 1
        else:
            output = self.outputs[-1]
        return output


def get_basic_commands() -> list[Command]:
    """Return a list of basic commands for testing."""
    return [
        Command(name="ls", docstring="List files"),
        Command(name="cat", docstring="Display file contents"),
        Command(name="submit", docstring="Submit solution"),
        Command(name="echo", docstring="Echo text"),
        Command(name="exit", docstring="Exit agent"),
    ]


class TestTemplateConfig:
    def test_default_values(self):
        config = TemplateConfig()
        assert config.system_template == ""
        assert config.instance_template == ""
        assert "Observation" in config.next_step_template
        assert config.max_observation_length == 100_000

    def test_custom_values(self):
        config = TemplateConfig(
            system_template="You are a helpful assistant.",
            instance_template="Fix this bug: {{problem_statement}}",
            max_observation_length=50_000,
        )
        assert config.system_template == "You are a helpful assistant."
        assert "Fix this bug" in config.instance_template
        assert config.max_observation_length == 50_000

    def test_next_step_no_output_defaults_to_next_step(self):
        config = TemplateConfig(next_step_template="Output: {{observation}}")
        assert config.next_step_no_output_template == "Output: {{observation}}"


class TestAgentHook:
    def test_default_methods_do_nothing(self):
        hook = AgentHook()
        hook.on_init(agent=None)
        hook.on_setup_attempt()
        hook.on_setup_done()
        hook.on_step_start()
        hook.on_step_done(step=None)
        hook.on_query_message_added()
        hook.on_run_start()
        hook.on_run_done(result=None)
        hook.on_tools_installation_started()


class TestCombinedAgentHook:
    def test_aggregates_hooks(self):
        combined = CombinedAgentHook()
        events = []

        class TrackingHook(AgentHook):
            def __init__(self, name: str):
                self.name = name

            def on_setup_done(self):
                events.append(f"{self.name}_setup")

            def on_step_done(self, *, step):
                events.append(f"{self.name}_step")

        combined.add_hook(TrackingHook("first"))
        combined.add_hook(TrackingHook("second"))

        combined.on_setup_done()
        combined.on_step_done(step=None)

        assert events == ["first_setup", "second_setup", "first_step", "second_step"]

    def test_all_lifecycle_methods(self):
        combined = CombinedAgentHook()
        events = []

        class AllEventsHook(AgentHook):
            def on_init(self, *, agent):
                events.append("init")

            def on_setup_attempt(self):
                events.append("setup_attempt")

            def on_setup_done(self):
                events.append("setup_done")

            def on_step_start(self):
                events.append("step_start")

            def on_step_done(self, *, step):
                events.append("step_done")

            def on_run_start(self):
                events.append("run_start")

            def on_run_done(self, *, result):
                events.append("run_done")

        combined.add_hook(AllEventsHook())

        combined.on_init(agent=None)
        combined.on_setup_attempt()
        combined.on_setup_done()
        combined.on_step_start()
        combined.on_step_done(step=None)
        combined.on_run_start()
        combined.on_run_done(result=None)

        assert events == [
            "init",
            "setup_attempt",
            "setup_done",
            "step_start",
            "step_done",
            "run_start",
            "run_done",
        ]


class TestAgentConfig:
    def test_default_values(self):
        config = AgentConfig()
        assert config.name == "main"
        assert config.max_requeries == 3
        assert config.max_steps == 100

    def test_custom_values(self):
        config = AgentConfig(
            name="custom",
            max_requeries=5,
            max_steps=50,
        )
        assert config.name == "custom"
        assert config.max_requeries == 5
        assert config.max_steps == 50


class TestDefaultAgent:
    @pytest.fixture
    def mock_model(self):
        return MockModel()

    @pytest.fixture
    def mock_env(self):
        return MockEnvironment()

    @pytest.fixture
    def problem(self):
        return TextProblemStatement(text="Fix the bug in auth.py")

    @pytest.fixture
    def agent(self, mock_model):
        templates = TemplateConfig(
            system_template="You are a coding assistant.",
            instance_template="Problem: {{problem_statement}}",
        )
        tools = ToolHandler(ToolConfig(), get_basic_commands())
        return DefaultAgent(
            templates=templates,
            tools=tools,
            history_processors=[DefaultHistoryProcessor()],
            model=mock_model,
            max_requeries=2,
            max_steps=10,
        )

    def test_creates_agent(self, agent):
        assert agent.name == "main"
        assert agent.max_requeries == 2
        assert agent.max_steps == 10

    def test_from_config(self, mock_model):
        config = AgentConfig(name="test_agent", max_steps=5)
        agent = DefaultAgent.from_config(config, mock_model)
        assert agent.name == "test_agent"
        assert agent.max_steps == 5

    def test_add_hook(self, agent):
        events = []

        class TestHook(AgentHook):
            def on_init(self, *, agent):
                events.append("init")

        agent.add_hook(TestHook())
        assert "init" in events

    def test_setup_creates_history(self, agent, problem):
        agent.setup(problem_statement=problem)

        assert len(agent.history) >= 2
        assert agent.history[0]["role"] == "system"
        assert agent.history[1]["role"] == "user"
        assert problem.get_problem_statement() in agent.history[1]["content"]

    def test_setup_creates_trajectory_path(self, agent, problem):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent.setup(
                problem_statement=problem,
                output_dir=Path(tmpdir),
            )
            assert agent.traj_path is not None
            assert problem.id in str(agent.traj_path)

    def test_step_queries_model(self, agent, problem, mock_model):
        agent.setup(problem_statement=problem)
        agent.step()

        assert len(mock_model.queries) == 1

    def test_step_executes_action_in_env(self, agent, problem, mock_env):
        agent.setup(problem_statement=problem, env=mock_env)
        agent.step()

        assert len(mock_env.commands) >= 1

    def test_step_records_trajectory(self, agent, problem):
        agent.setup(problem_statement=problem)
        agent.step()

        assert len(agent.trajectory) == 1
        assert "action" in agent.trajectory[0]
        assert "observation" in agent.trajectory[0]

    def test_step_handles_no_env(self, agent, problem):
        agent.setup(problem_statement=problem)
        step = agent.step()

        assert step.observation is not None
        assert "No environment" in step.observation

    def test_step_returns_step_output(self, agent, problem, mock_env):
        agent.setup(problem_statement=problem, env=mock_env)
        step = agent.step()

        assert isinstance(step, StepOutput)
        assert step.action is not None
        assert step.observation is not None

    def test_max_steps_terminates(self, agent, problem, mock_env):
        agent.max_steps = 2
        agent.setup(problem_statement=problem, env=mock_env)

        step1 = agent.step()
        assert not step1.done

        step2 = agent.step()
        assert not step2.done

        step3 = agent.step()
        assert step3.done
        assert step3.exit_status == "max_steps_reached"

    def test_messages_property_filters_by_agent(self, agent, problem):
        agent.setup(problem_statement=problem)
        messages = agent.messages

        for msg in messages:
            assert msg.get("agent") == agent.name

    def test_run_completes_loop(self, problem, mock_env):
        model = MockModel([
            {
                "message": "Let me list files",
                "tool_calls": [{"function": {"name": "ls", "arguments": "{}"}}],
            },
            {
                "message": "Submitting",
                "tool_calls": [{"function": {"name": "submit", "arguments": "{}"}}],
            },
        ])
        mock_env.outputs = [
            "file1.txt",
            "<<SWE_AGENT_SUBMISSION>>\nSubmission complete",
        ]

        templates = TemplateConfig(
            system_template="You are a coding assistant.",
            instance_template="Problem: {{problem_statement}}",
        )
        tools = ToolHandler(ToolConfig(), get_basic_commands())
        agent = DefaultAgent(
            templates=templates,
            tools=tools,
            history_processors=[DefaultHistoryProcessor()],
            model=model,
            max_steps=10,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = agent.run(
                problem_statement=problem,
                env=mock_env,
                output_dir=Path(tmpdir),
            )

            assert result is not None
            assert result.info.get("exit_status") == "submitted"
            assert len(result.trajectory) >= 1

    def test_save_trajectory(self, agent, problem):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent.setup(
                problem_statement=problem,
                output_dir=Path(tmpdir),
            )
            agent.step()
            agent.save_trajectory()

            assert agent.traj_path.exists()
            data = json.loads(agent.traj_path.read_text())
            assert "trajectory" in data
            assert "history" in data
            assert "info" in data

    def test_get_trajectory_data(self, agent, problem):
        agent.setup(problem_statement=problem)
        agent.step()

        data = agent.get_trajectory_data()
        assert "trajectory" in data
        assert "history" in data
        assert "info" in data
        assert len(data["trajectory"]) == 1


class TestAgentWithSubmission:
    def test_detects_submission(self):
        model = MockModel([
            {
                "message": "Submitting",
                "tool_calls": [{"function": {"name": "submit", "arguments": "{}"}}],
            }
        ])
        env = MockEnvironment(["<<SWE_AGENT_SUBMISSION>>\nDiff here"])

        templates = TemplateConfig(
            system_template="",
            instance_template="{{problem_statement}}",
        )
        tools = ToolHandler(ToolConfig(), get_basic_commands())
        agent = DefaultAgent(
            templates=templates,
            tools=tools,
            history_processors=[DefaultHistoryProcessor()],
            model=model,
        )

        problem = TextProblemStatement(text="Test")
        agent.setup(problem_statement=problem, env=env)
        step = agent.step()

        assert step.done is True
        assert step.exit_status == "submitted"


class TestAgentHooksIntegration:
    def test_hooks_called_during_run(self):
        events = []

        class TrackingHook(AgentHook):
            def on_run_start(self):
                events.append("run_start")

            def on_setup_attempt(self):
                events.append("setup_attempt")

            def on_setup_done(self):
                events.append("setup_done")

            def on_step_start(self):
                events.append("step_start")

            def on_step_done(self, *, step):
                events.append("step_done")

            def on_run_done(self, *, result):
                events.append("run_done")

        model = MockModel([
            {
                "message": "Exiting",
                "tool_calls": [{"function": {"name": "exit", "arguments": "{}"}}],
            }
        ])
        env = MockEnvironment(["<<SWE_AGENT_SUBMISSION>>"])

        templates = TemplateConfig()
        tools = ToolHandler(ToolConfig(), get_basic_commands())
        agent = DefaultAgent(
            templates=templates,
            tools=tools,
            history_processors=[DefaultHistoryProcessor()],
            model=model,
            max_steps=1,
        )
        agent.add_hook(TrackingHook())

        problem = TextProblemStatement(text="Test")
        with tempfile.TemporaryDirectory() as tmpdir:
            agent.run(
                problem_statement=problem,
                env=env,
                output_dir=Path(tmpdir),
            )

        assert "run_start" in events
        assert "setup_attempt" in events
        assert "setup_done" in events
        assert "step_start" in events
        assert "step_done" in events
        assert "run_done" in events


class TestAgentErrorHandling:
    def test_handles_model_format_error(self):
        model = MockModel([
            {"message": "No tool call here"},  # Missing tool_calls
            {"message": "Still no tool call"},  # Missing tool_calls
            {
                "message": "Now with tool call",
                "tool_calls": [{"function": {"name": "ls", "arguments": "{}"}}],
            },
        ])
        env = MockEnvironment(["output"])

        templates = TemplateConfig()
        tools = ToolHandler(ToolConfig(), get_basic_commands())
        agent = DefaultAgent(
            templates=templates,
            tools=tools,
            history_processors=[DefaultHistoryProcessor()],
            model=model,
            max_requeries=2,
        )

        problem = TextProblemStatement(text="Test")
        agent.setup(problem_statement=problem, env=env)
        step = agent.step()

        assert step.action == "ls"

    def test_exhausts_retries_on_format_error(self):
        model = MockModel([{"message": "No valid output"}] * 10)
        env = MockEnvironment(["output"])

        templates = TemplateConfig()
        tools = ToolHandler(ToolConfig(), get_basic_commands())
        agent = DefaultAgent(
            templates=templates,
            tools=tools,
            history_processors=[DefaultHistoryProcessor()],
            model=model,
            max_requeries=2,
        )

        problem = TextProblemStatement(text="Test")
        agent.setup(problem_statement=problem, env=env)
        step = agent.step()

        assert step.done is True
        assert step.exit_status == "format_error"
