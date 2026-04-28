from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
from swerex.deployment.config import DeploymentConfig, DummyDeploymentConfig

from sweagent.environment.hooks.abstract import EnvHook
from sweagent.environment.repo import RepoConfig


class EnvironmentConfig(BaseModel):
    """Configuration for the SWE environment."""

    deployment: DeploymentConfig = DummyDeploymentConfig()
    repo: RepoConfig | None = None
    post_startup_commands: list[str] = []

    class Config:
        arbitrary_types_allowed = True


class SWEEnv:
    """SWE agent environment."""

    deployment: Any
    repo: RepoConfig | None

    def __init__(self, config: EnvironmentConfig):
        self.config = config
        self.deployment = None
        self.repo = config.repo
        self._hooks: list[EnvHook] = []

    @classmethod
    def from_config(cls, config: EnvironmentConfig) -> "SWEEnv":
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    def add_hook(self, hook: EnvHook) -> None:
        raise NotImplementedError

    def communicate(
        self,
        command: str,
        check: str = "ignore",
        error_msg: str = "",
        timeout: float | None = None,
    ) -> str:
        raise NotImplementedError

    def read_file(self, path: Path) -> str:
        raise NotImplementedError

    def write_file(self, path: str, content: str) -> None:
        raise NotImplementedError

    def interrupt_session(self) -> None:
        raise NotImplementedError
