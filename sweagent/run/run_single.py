from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
from swerex.deployment.config import DeploymentConfig

from sweagent.agent.agents import DefaultAgent, DefaultAgentConfig
from sweagent.environment.swe_env import EnvironmentConfig
from sweagent.run.hooks.abstract import RunHook


class RunSingleConfig(BaseModel):
    """Configuration for a single run."""

    agent: DefaultAgentConfig
    env: EnvironmentConfig = EnvironmentConfig()
    output_dir: Path | None = None

    class Config:
        arbitrary_types_allowed = True


class RunSingle:
    """Run a single instance."""

    agent: DefaultAgent

    def __init__(self, config: RunSingleConfig):
        self.config = config
        self._hooks: list[RunHook] = []

    @classmethod
    def from_config(cls, config: RunSingleConfig) -> "RunSingle":
        raise NotImplementedError

    def add_hook(self, hook: RunHook) -> None:
        raise NotImplementedError

    def run(self) -> Any:
        raise NotImplementedError
