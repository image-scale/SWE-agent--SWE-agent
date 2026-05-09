"""Agent that orchestrates model, tools, environment, and history."""

from __future__ import annotations

import copy
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from jinja2 import Template
from pydantic import BaseModel, ConfigDict, Field

from codeagent.agent.hooks import AgentHook, CombinedAgentHook
from codeagent.agent.templates import TemplateConfig
from codeagent.exceptions import (
    ContextWindowExceededError,
    CostLimitExceededError,
    FormatError,
)
from codeagent.history import DefaultHistoryProcessor
from codeagent.problem import ProblemStatement
from codeagent.tools import ToolConfig, ToolHandler
from codeagent.types import AgentInfo, AgentRunResult, StepOutput, TrajectoryStep

if TYPE_CHECKING:
    from codeagent.models import AbstractModel


logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Configuration for the agent."""

    name: str = "main"
    """Name of the agent."""

    templates: TemplateConfig = Field(default_factory=TemplateConfig)
    """Template configuration for messages."""

    tools: ToolConfig = Field(default_factory=ToolConfig)
    """Tool configuration."""

    max_requeries: int = 3
    """Maximum retries after format/syntax errors."""

    max_steps: int = 100
    """Maximum number of steps before termination."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


class _BlockedActionError(Exception):
    """Raised when an action is blocked."""


class DefaultAgent:
    """Agent that orchestrates model, tools, environment, and history to solve problems.

    The agent handles:
    - Formatting prompts and processing model responses
    - Managing conversation history
    - Executing actions in the environment
    - Tracking trajectory and statistics

    To use, either call `run()` for a complete solution attempt, or call
    `setup()` followed by `step()` in a loop for fine-grained control.
    """

    def __init__(
        self,
        *,
        templates: TemplateConfig,
        tools: ToolHandler,
        history_processors: list,
        model: Any,
        max_requeries: int = 3,
        max_steps: int = 100,
        name: str = "main",
    ):
        """Initialize the agent.

        Args:
            templates: Template configuration
            tools: Tool handler
            history_processors: History processors
            model: Language model
            max_requeries: Max retries on errors
            max_steps: Max steps per run
            name: Agent name
        """
        self.name = name
        self.model = model
        self.templates = templates
        self.tools = tools
        self.history_processors = history_processors
        self.max_requeries = max_requeries
        self.max_steps = max_steps

        self._problem_statement: ProblemStatement | None = None
        self._env: Any = None
        self.traj_path: Path | None = None

        self.history: list[dict[str, Any]] = []
        self._trajectory: list[TrajectoryStep] = []
        self.info = AgentInfo()

        self._chook = CombinedAgentHook()
        self._step_count = 0

    @classmethod
    def from_config(cls, config: AgentConfig, model: "AbstractModel", history_processors: list | None = None) -> "DefaultAgent":
        """Create agent from configuration.

        Args:
            config: Agent configuration
            model: Language model instance
            history_processors: Optional history processors (defaults to DefaultHistoryProcessor)

        Returns:
            Configured agent
        """
        config = config.model_copy(deep=True)
        return cls(
            templates=config.templates,
            tools=ToolHandler(config.tools),
            history_processors=history_processors or [DefaultHistoryProcessor()],
            model=model,
            max_requeries=config.max_requeries,
            max_steps=config.max_steps,
            name=config.name,
        )

    def add_hook(self, hook: AgentHook) -> None:
        """Add a hook to the agent."""
        hook.on_init(agent=self)
        self._chook.add_hook(hook)

    @property
    def trajectory(self) -> list[TrajectoryStep]:
        """Get the trajectory of steps taken."""
        return self._trajectory

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Get processed history for the model."""
        filtered = [h for h in self.history if h.get("agent") == self.name]
        messages = filtered
        for processor in self.history_processors:
            messages = processor(messages)
        return messages

    def _append_history(self, item: dict[str, Any]) -> None:
        """Add an item to history."""
        self._chook.on_query_message_added(**item)
        self.history.append(item)

    def setup(
        self,
        *,
        problem_statement: ProblemStatement,
        env: Any = None,
        output_dir: Path = Path("."),
    ) -> None:
        """Set up the agent for a new problem.

        Args:
            problem_statement: The problem to solve
            env: Optional environment for command execution
            output_dir: Directory for output files
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        self._problem_statement = problem_statement
        self._env = env
        self.traj_path = output_dir / f"{problem_statement.id}.traj"

        self._chook.on_setup_attempt()

        self.history = []
        self._trajectory = []
        self.info = AgentInfo()
        self._step_count = 0

        self._add_system_message()
        self._add_instance_template()

        self._chook.on_setup_done()
        logger.info("Agent setup complete for %s", problem_statement.id)

    def _get_format_dict(self, **kwargs: Any) -> dict[str, Any]:
        """Get the format dictionary for templates."""
        assert self._problem_statement is not None
        base = {
            "problem_statement": self._problem_statement.get_problem_statement(),
            "command_docs": self.tools.generate_command_docs(),
            **self._problem_statement.get_extra_fields(),
            **kwargs,
        }
        if self._env is not None and hasattr(self._env, "repo") and self._env.repo:
            base["repo"] = self._env.repo.repo_name
        return base

    def _add_system_message(self) -> None:
        """Add the system message to history."""
        content = Template(self.templates.system_template).render(
            **self._get_format_dict()
        )
        self._append_history({
            "role": "system",
            "content": content,
            "agent": self.name,
            "message_type": "system_prompt",
        })
        logger.debug("System message: %s", content[:200])

    def _add_instance_template(self) -> None:
        """Add the instance template to history."""
        content = Template(self.templates.instance_template).render(
            **self._get_format_dict()
        )
        self._append_history({
            "role": "user",
            "content": content,
            "agent": self.name,
            "message_type": "instance",
        })
        logger.debug("Instance message: %s", content[:200])

    def _add_observation_to_history(
        self,
        observation: str,
        tool_call_ids: list[str] | None = None,
    ) -> None:
        """Add an observation to history."""
        elided_chars = 0
        max_len = self.templates.max_observation_length

        if observation.strip() == "":
            template = self.templates.next_step_no_output_template or ""
        elif len(observation) > max_len:
            template = self.templates.next_step_truncated_observation_template
            elided_chars = len(observation) - max_len
        else:
            template = self.templates.next_step_template

        content = Template(template).render(
            observation=observation,
            max_observation_length=max_len,
            elided_chars=elided_chars,
            **self._get_format_dict(),
        )

        item: dict[str, Any] = {
            "role": "user" if not tool_call_ids else "tool",
            "content": content,
            "agent": self.name,
            "message_type": "observation",
        }
        if tool_call_ids:
            item["tool_call_ids"] = tool_call_ids

        self._append_history(item)

    def step(self) -> StepOutput:
        """Execute one step of the agent loop.

        Returns:
            StepOutput with the action taken and observation
        """
        self._chook.on_step_start()
        self._step_count += 1

        if self._step_count > self.max_steps:
            logger.warning("Max steps reached")
            return StepOutput(
                done=True,
                exit_status="max_steps_reached",
                observation="Maximum number of steps reached.",
            )

        step = StepOutput()
        start_time = time.time()

        try:
            step = self._execute_step(step)
        except CostLimitExceededError as e:
            logger.error("Cost limit exceeded: %s", e)
            step.done = True
            step.exit_status = "cost_limit"
            step.observation = str(e)
        except ContextWindowExceededError as e:
            logger.error("Context window exceeded: %s", e)
            step.done = True
            step.exit_status = "context_window"
            step.observation = str(e)
        except Exception as e:
            logger.exception("Unexpected error in step")
            step.done = True
            step.exit_status = "error"
            step.observation = f"Error: {e}"

        step.execution_time = time.time() - start_time

        self._record_step(step)
        self._chook.on_step_done(step=step)

        return step

    def _execute_step(self, step: StepOutput) -> StepOutput:
        """Execute a single step with retries for format errors."""
        for attempt in range(self.max_requeries + 1):
            try:
                response = self.model.query(self.messages)
                step.query = response

                thought, action = self._parse_response(response)
                step.thought = thought
                step.action = action

                if self.tools.should_block_action(action):
                    raise _BlockedActionError(f"Action blocked: {action}")

                observation = self._execute_action(action)
                step.observation = observation

                if self.tools.check_for_submission_cmd(observation):
                    step.done = True
                    step.exit_status = "submitted"
                    step.submission = observation

                break

            except FormatError as e:
                if attempt < self.max_requeries:
                    logger.warning("Format error, retrying: %s", e)
                    self._add_format_error_to_history(str(e), step.query or "")
                else:
                    step.observation = f"Format error after {self.max_requeries} retries: {e}"
                    step.exit_status = "format_error"
                    step.done = True

            except _BlockedActionError as e:
                if attempt < self.max_requeries:
                    logger.warning("Blocked action, retrying: %s", e)
                    self._add_blocked_action_to_history(step.action or "")
                else:
                    step.observation = f"Blocked action after {self.max_requeries} retries"
                    step.exit_status = "blocked"
                    step.done = True

        return step

    def _parse_response(self, response: dict[str, Any] | str) -> tuple[str, str]:
        """Parse model response into thought and action."""
        if isinstance(response, str):
            thought, action = self.tools.parse_actions({"message": response})
        else:
            thought, action = self.tools.parse_actions(response)
        return thought, action

    def _execute_action(self, action: str) -> str:
        """Execute an action and return the observation."""
        if self._env is None:
            return f"[No environment configured. Action: {action}]"

        try:
            return self._env.communicate(action)
        except Exception as e:
            return f"Error executing action: {e}"

    def _add_format_error_to_history(self, error: str, output: str) -> None:
        """Add format error feedback to history."""
        content = Template(self.templates.format_error_template).render(
            expected_format="Please provide your response with a clear action.",
            output=output,
            error=error,
        )
        self._append_history({
            "role": "user",
            "content": content,
            "agent": self.name,
            "message_type": "error",
        })

    def _add_blocked_action_to_history(self, action: str) -> None:
        """Add blocked action feedback to history."""
        content = Template(self.templates.blocked_action_template).render(
            action=action,
        )
        self._append_history({
            "role": "user",
            "content": content,
            "agent": self.name,
            "message_type": "error",
        })

    def _record_step(self, step: StepOutput) -> None:
        """Record step in trajectory and history."""
        query = step.query
        if isinstance(query, dict):
            query = query.get("message", str(query))

        traj_step: TrajectoryStep = {
            "action": step.action or "",
            "observation": step.observation or "",
            "response": query or "",
            "state": step.state or {},
            "thought": step.thought or "",
            "execution_time": step.execution_time or 0.0,
            "query": [],
            "extra_info": step.extra_info or {},
        }
        self._trajectory.append(traj_step)

        if step.action:
            self._append_history({
                "role": "assistant",
                "content": step.output or "",
                "thought": step.thought,
                "action": step.action,
                "agent": self.name,
                "message_type": "action",
            })

        if step.observation and not step.done:
            self._add_observation_to_history(
                step.observation,
                step.tool_call_ids,
            )

    def run(
        self,
        *,
        problem_statement: ProblemStatement,
        env: Any = None,
        output_dir: Path = Path("."),
    ) -> AgentRunResult:
        """Run the agent on a problem.

        Args:
            problem_statement: Problem to solve
            env: Optional environment
            output_dir: Output directory

        Returns:
            AgentRunResult with trajectory and info
        """
        self._chook.on_run_start()
        self.setup(
            problem_statement=problem_statement,
            env=env,
            output_dir=output_dir,
        )

        while True:
            step = self.step()
            if step.done:
                break

        self.info["exit_status"] = step.exit_status
        self.info["submission"] = step.submission
        self.info["model_stats"] = self.model.stats.model_dump()

        self.save_trajectory()

        result = AgentRunResult(
            info=self.info,
            trajectory=self._trajectory,
        )
        self._chook.on_run_done(result=result)

        return result

    def get_trajectory_data(self) -> dict[str, Any]:
        """Get trajectory data for saving."""
        return {
            "trajectory": self._trajectory,
            "history": copy.deepcopy(self.history),
            "info": dict(self.info),
        }

    def save_trajectory(self) -> None:
        """Save trajectory to disk."""
        if self.traj_path is None:
            return
        data = self.get_trajectory_data()
        self.traj_path.write_text(json.dumps(data, indent=2))
        logger.info("Trajectory saved to %s", self.traj_path)
