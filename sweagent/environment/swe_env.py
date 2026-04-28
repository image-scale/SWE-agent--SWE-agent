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
        """Create an SWEEnv from configuration."""
        env = cls(config)
        # Create the deployment from the config
        env.deployment = config.deployment.get_deployment()
        return env

    def start(self) -> None:
        """Start the environment."""
        if self.deployment is not None:
            self.deployment.start()

    def close(self) -> None:
        """Close the environment."""
        if self.deployment is not None:
            self.deployment.stop()

    def reset(self) -> None:
        """Reset the environment."""
        # Reset repo if configured
        if self.repo is not None:
            reset_commands = self.repo.get_reset_commands()
            for cmd in reset_commands:
                self.communicate(cmd)

    def add_hook(self, hook: EnvHook) -> None:
        """Add a hook to the environment."""
        self._hooks.append(hook)

    def communicate(
        self,
        command: str,
        check: str = "ignore",
        error_msg: str = "",
        timeout: float | None = None,
    ) -> str:
        """Execute a command in the environment."""
        if self.deployment is None or self.deployment.runtime is None:
            return ""
        return ""

    def read_file(self, path: Path) -> str:
        """Read a file from the environment."""
        if self.deployment is None or self.deployment.runtime is None:
            return ""
        return ""

    def write_file(self, path: str, content: str) -> None:
        """Write a file in the environment."""
        pass

    def interrupt_session(self) -> None:
        """Interrupt the current session."""
        pass
