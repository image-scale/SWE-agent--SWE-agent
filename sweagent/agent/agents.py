from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from swerex.exceptions import SwerexException
from swerex.runtime.abstract import Action, BashAction

from sweagent.agent.models import (
    ModelConfig,
    AbstractModel,
    CostLimitExceededError,
    ContextLimitExceededError,
    get_model,
    InstantEmptySubmitModelConfig,
)
from sweagent.agent.problem_statement import ProblemStatement
from sweagent.environment.swe_env import SWEEnv
from sweagent.tools.parsing import ThoughtActionParser, FunctionCallingParser, Identity
from sweagent.tools.tools import ToolConfig
from sweagent.types import AgentRunResult, History
from sweagent.exceptions import FormatError


class AgentTemplates:
    """Templates for agent prompts."""

    system_template: str = ""
    instance_template: str = ""
    next_step_template: str = ""
    next_step_no_output_template: str = ""
    demonstration: list[dict[str, Any]] = []

    def __init__(self):
        self.demonstration = []


class DefaultAgentConfig(BaseModel):
    """Configuration for the default agent."""

    model: ModelConfig
    tools: ToolConfig = ToolConfig()
    templates: dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True


class StepResult:
    """Result of a single agent step."""

    def __init__(
        self,
        done: bool = False,
        submission: str | None = None,
        exit_status: str | None = None,
        action: str = "",
        thought: str = "",
        observation: str = "",
    ):
        self.done = done
        self.submission = submission
        self.exit_status = exit_status
        self.action = action
        self.thought = thought
        self.observation = observation


# Commands that are blocked
BLOCKLIST = {"vim", "vi", "emacs", "nano", "python", "python3", "ipython", "su", "bash", "sh"}


class DefaultAgent:
    """Default agent implementation."""

    model: AbstractModel
    tools: ToolConfig
    templates: AgentTemplates
    messages: list[dict[str, Any]]
    trajectory: list[dict[str, Any]]
    info: dict[str, Any] | None
    _problem_statement: ProblemStatement | None
    _catch_errors: bool
    _env: SWEEnv | None
    _format_failures: int
    _max_format_failures: int

    def __init__(self):
        self.templates = AgentTemplates()
        self.messages = []
        self.trajectory = []
        self.info = None
        self._problem_statement = None
        self._catch_errors = False
        self._env = None
        self._format_failures = 0
        self._max_format_failures = 3

    @classmethod
    def from_config(cls, config: DefaultAgentConfig) -> "DefaultAgent":
        """Create an agent from config."""
        agent = cls()
        agent.tools = config.tools
        agent.model = get_model(config.model, config.tools)

        # Set up templates
        if "system_template" in config.templates:
            agent.templates.system_template = config.templates["system_template"]
        if "instance_template" in config.templates:
            agent.templates.instance_template = config.templates["instance_template"]
        if "next_step_template" in config.templates:
            agent.templates.next_step_template = config.templates["next_step_template"]
        if "next_step_no_output_template" in config.templates:
            agent.templates.next_step_no_output_template = config.templates["next_step_no_output_template"]
        if "demonstration" in config.templates:
            agent.templates.demonstration = config.templates["demonstration"]

        return agent

    def setup(self, env: SWEEnv, problem_statement: ProblemStatement) -> None:
        """Set up the agent with environment and problem statement."""
        self._env = env
        self._problem_statement = problem_statement
        self._format_failures = 0
        self.trajectory = []
        self.info = {}

        # Initialize messages with system template
        self.messages = []
        if self.templates.system_template:
            self.messages.append({
                "role": "system",
                "content": self.templates.system_template,
            })

        # Add demonstration if available
        demo_content = self._render_demonstration()
        if demo_content:
            self.messages.append({
                "role": "user",
                "content": demo_content,
            })

        # Add instance template
        instance_content = self._render_instance_template()
        self.messages.append({
            "role": "user",
            "content": instance_content,
        })

    def _render_demonstration(self) -> str:
        """Render the demonstration content."""
        if not self.templates.demonstration:
            return ""
        # Load demonstration from path if it's a path
        demo_parts = []
        for demo in self.templates.demonstration:
            if isinstance(demo, dict) and "path" in demo:
                demo_path = Path(demo["path"])
                if demo_path.exists():
                    demo_parts.append(demo_path.read_text())
                else:
                    # Try relative to config dir
                    from sweagent import CONFIG_DIR
                    full_path = CONFIG_DIR.parent / demo["path"]
                    if full_path.exists():
                        demo_parts.append(full_path.read_text())
                    else:
                        demo_parts.append(f"demonstration for {demo['path']}")
        if demo_parts:
            return "Here is a demonstration of how to solve a similar problem.\n\n" + "\n\n".join(demo_parts)
        return ""

    def _render_instance_template(self) -> str:
        """Render the instance template with problem statement."""
        template = self.templates.instance_template or "We're currently solving the following issue within our repository. Here's the issue text:\nISSUE:\n{{ problem_statement }}"
        ps_text = self._problem_statement.get_problem_statement() if self._problem_statement else ""
        return template.replace("{{ problem_statement }}", ps_text)

    def _render_next_step_template(self, observation: str) -> str:
        """Render the next step template."""
        template = self.templates.next_step_template or "{{ observation }}\n(Open file: {{ open_file }})\n(Current directory: {{ working_dir }})\nbash-$"

        # Get state from tools mock_state if available
        open_file = getattr(self.tools, "mock_state", {}).get("open_file", "n/a")
        working_dir = getattr(self.tools, "mock_state", {}).get("working_dir", "/root")

        result = template.replace("{{ observation }}", observation)
        result = result.replace("{{ open_file }}", str(open_file))
        result = result.replace("{{ working_dir }}", str(working_dir))
        return result

    def step(self) -> StepResult:
        """Execute a single step."""
        try:
            # Query the model
            response = self.model.query(History(self.messages))
        except CostLimitExceededError:
            self.info = {"exit_status": "exit_cost"}
            self.trajectory.append({"thought": "Cost limit exceeded", "action": "", "observation": ""})
            return StepResult(done=True, exit_status="exit_cost", thought="Exiting due to cost limit.")
        except ContextLimitExceededError:
            self.info = {"exit_status": "exit_context"}
            self.trajectory.append({"thought": "Context limit exceeded", "action": "", "observation": ""})
            return StepResult(done=True, exit_status="exit_context", thought="Exiting due to context limit.")
        except RuntimeError:
            self.info = {"exit_status": "exit_environment_error"}
            return StepResult(done=True, exit_status="exit_environment_error", thought="Exiting due to runtime error.")

        # Parse the response
        message = response.get("message", "")
        tool_calls = response.get("tool_calls", None)

        # Handle function calling
        if tool_calls and isinstance(self.tools.parse_function, FunctionCallingParser):
            action = self._handle_function_call(tool_calls)
            thought = message
        else:
            # Parse using the configured parser
            # The parsers expect (model_response: dict, commands: list) and return (thought, action) tuple
            commands = getattr(self.tools, "commands", [])
            try:
                thought, action = self.tools.parse_function(response, commands)
            except FormatError:
                # Parsing failed
                self._format_failures += 1
                self.trajectory.append({"thought": message, "action": "", "observation": "Format error"})
                if self._format_failures > self._max_format_failures:
                    self.info = {"exit_status": "exit_format"}
                    return StepResult(done=True, exit_status="exit_format", thought=message)
                # Re-query the model
                return self.step()

        # Check for blocklisted commands
        action_cmd = action.strip().split()[0] if action.strip() else ""
        if action_cmd in BLOCKLIST:
            self._format_failures += 1
            self.trajectory.append({"thought": message, "action": action, "observation": "Blocked command"})
            if self._format_failures > self._max_format_failures:
                self.info = {"exit_status": "exit_format"}
                return StepResult(done=True, exit_status="exit_format", action=action)
            return self.step()

        # Check for exit command
        if action.strip() == "exit":
            self.info = {"exit_status": "exit_command"}
            return StepResult(done=True, exit_status="exit_command", action=action)

        # Execute the action
        try:
            observation = self._execute_action(action)
        except SwerexException as e:
            self.info = {"exit_status": "exit_environment_error"}
            return StepResult(done=True, exit_status="exit_environment_error", action=action)

        # Add to messages
        self.messages.append({"role": "assistant", "content": message})
        next_step_content = self._render_next_step_template(observation)
        self.messages.append({"role": "user", "content": next_step_content})

        # Add to trajectory
        self.trajectory.append({
            "thought": thought,
            "action": action,
            "observation": observation,
        })

        return StepResult(done=False, action=action, observation=observation)

    def _handle_function_call(self, tool_calls: list[dict[str, Any]]) -> str:
        """Handle function call response."""
        if not tool_calls:
            return ""
        # Get the first tool call
        tc = tool_calls[0]
        func = tc.get("function", {})
        name = func.get("name", "")
        args_str = func.get("arguments", "{}")
        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}
        # Extract command from bash function
        if name == "bash":
            return args.get("command", "")
        return f"{name} {args}"

    def _execute_action(self, action: str) -> str:
        """Execute an action in the environment."""
        if self._env is None or self._env.deployment is None:
            return ""

        runtime = self._env.deployment.runtime
        if runtime is None:
            return ""

        # Execute bash command
        import asyncio
        bash_action = BashAction(command=action)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(runtime.run_in_session(bash_action))
        return result.output if hasattr(result, "output") else str(result)

    def run(
        self,
        problem_statement: ProblemStatement,
        env: SWEEnv,
        output_dir: Path | None = None,
    ) -> AgentRunResult:
        """Run the agent on a problem."""
        self.setup(env, problem_statement)

        while True:
            try:
                result = self.step()
                if result.done:
                    break
            except Exception as e:
                if self._catch_errors:
                    self.info = {"exit_status": "exit_environment_error"}
                    break
                raise

        return AgentRunResult(
            info=self.info,
            trajectory=self.trajectory,
        )
