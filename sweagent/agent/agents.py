from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sweagent.agent.models import ModelConfig, AbstractModel
from sweagent.agent.problem_statement import ProblemStatement
from sweagent.environment.swe_env import SWEEnv
from sweagent.tools.tools import ToolConfig
from sweagent.types import AgentRunResult


class AgentTemplates:
    """Templates for agent prompts."""

    next_step_no_output_template: str = ""


class DefaultAgentConfig(BaseModel):
    """Configuration for the default agent."""

    model: ModelConfig
    tools: ToolConfig = ToolConfig()


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

    def __init__(self):
        self.templates = AgentTemplates()
        self.messages = []
        self.trajectory = []
        self.info = None
        self._problem_statement = None
        self._catch_errors = False

    @classmethod
    def from_config(cls, config: DefaultAgentConfig) -> "DefaultAgent":
        raise NotImplementedError

    def setup(self, env: SWEEnv, problem_statement: ProblemStatement) -> None:
        raise NotImplementedError

    def step(self) -> StepResult:
        raise NotImplementedError

    def run(
        self,
        problem_statement: ProblemStatement,
        env: SWEEnv,
        output_dir: Path | None = None,
    ) -> AgentRunResult:
        raise NotImplementedError
