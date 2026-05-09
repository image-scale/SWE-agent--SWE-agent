"""SWE Environment for managing runtime execution."""

import logging
import shlex
import subprocess
from pathlib import Path, PurePath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from codeagent.environment.hooks import CombinedEnvHooks, EnvHook
from codeagent.environment.repo import Repo, RepoConfig


logger = logging.getLogger(__name__)


class EnvironmentConfig(BaseModel):
    """Configuration for the environment in which tasks are solved."""

    repo: RepoConfig | None = Field(
        default=None,
        description="Repository options.",
    )

    post_startup_commands: list[str] = Field(default_factory=list)
    """Commands to execute before starting the agent but after all other setup."""

    post_startup_command_timeout: int = 500
    """Timeout for each post-startup command."""

    working_directory: Path | None = None
    """Working directory for command execution. Defaults to repo directory if available."""

    env_variables: dict[str, str] = Field(
        default_factory=lambda: {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PAGER": "cat",
        }
    )
    """Environment variables to set."""

    name: str = "main"
    """Name of the environment."""

    model_config = ConfigDict(extra="forbid")


class SWEEnv:
    """Environment for executing commands and managing repository state.

    This class represents the environment in which tasks are solved.
    It manages command execution, repository operations, and lifecycle hooks.
    """

    def __init__(
        self,
        *,
        repo: Repo | RepoConfig | None = None,
        post_startup_commands: list[str] | None = None,
        post_startup_command_timeout: int = 500,
        hooks: list[EnvHook] | None = None,
        name: str = "main",
        working_directory: Path | None = None,
        env_variables: dict[str, str] | None = None,
    ):
        """Initialize the environment.

        Args:
            repo: Repository configuration
            post_startup_commands: Commands to execute on startup
            post_startup_command_timeout: Timeout for startup commands
            hooks: Environment hooks for lifecycle events
            name: Name of the environment
            working_directory: Working directory for commands
            env_variables: Environment variables to set
        """
        self.repo = repo
        self._post_startup_commands = post_startup_commands or []
        self.post_startup_command_timeout = post_startup_command_timeout
        self.name = name
        self._working_directory = working_directory
        self._env_variables = env_variables or {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PAGER": "cat",
        }
        self._started = False
        self._chook = CombinedEnvHooks()
        for hook in hooks or []:
            self.add_hook(hook)

    @classmethod
    def from_config(cls, config: EnvironmentConfig) -> "SWEEnv":
        """Create an environment instance from a configuration object."""
        config = config.model_copy(deep=True)
        return cls(
            repo=config.repo,
            post_startup_commands=config.post_startup_commands,
            post_startup_command_timeout=config.post_startup_command_timeout,
            name=config.name,
            working_directory=config.working_directory,
            env_variables=config.env_variables,
        )

    def add_hook(self, hook: EnvHook) -> None:
        """Add an EnvHook to the environment.

        This allows injecting custom functionality at different stages
        of the environment lifecycle.
        """
        hook.on_init(env=self)
        self._chook.add_hook(hook)

    @property
    def working_directory(self) -> Path | None:
        """Get the current working directory."""
        if self._working_directory:
            return self._working_directory
        if self.repo is not None:
            return Path(f"/{self.repo.repo_name}")
        return None

    def start(self) -> None:
        """Start the environment and reset it to a clean state."""
        self._chook.on_start_deployment()
        self._started = True
        self.reset()
        for command in self._post_startup_commands:
            self.communicate(
                command,
                check="raise",
                timeout=self.post_startup_command_timeout,
            )

    def reset(self) -> None:
        """Reset the environment to a clean state."""
        self._reset_repository()
        self._chook.on_environment_startup()

    def _reset_repository(self) -> None:
        """Clean repository of any modifications and checkout base commit."""
        if self.repo is None:
            return
        logger.debug(
            "Resetting repository %s to commit %s",
            self.repo.repo_name,
            self.repo.base_commit,
        )
        self._chook.on_copy_repo_started(self.repo)
        reset_commands = self.repo.get_reset_commands()
        if reset_commands:
            startup_commands = [
                f"cd /{self.repo.repo_name}",
                "export ROOT=$(pwd -P)",
                *reset_commands,
            ]
            self.communicate(
                " && ".join(startup_commands),
                check="raise",
                error_msg="Failed to reset repository",
                timeout=120,
            )

    def hard_reset(self) -> None:
        """Completely restart the environment."""
        self.close()
        self.start()

    def close(self) -> None:
        """Shutdown the environment."""
        logger.info("Beginning environment shutdown...")
        self._started = False
        self._chook.on_close()

    def communicate(
        self,
        input: str,
        timeout: int | float = 25,
        *,
        check: Literal["warn", "ignore", "raise"] = "ignore",
        error_msg: str = "Command failed",
    ) -> str:
        """Execute a command in the environment.

        Args:
            input: Command to execute
            timeout: Timeout duration in seconds
            check: Error handling mode
                - "ignore": Don't check exit code
                - "warn": Log warning on non-zero exit
                - "raise": Raise RuntimeError on non-zero exit
            error_msg: Error message prefix

        Returns:
            Command output
        """
        logger.debug("Input: %s", input)

        env = {**self._env_variables}
        cwd = str(self.working_directory) if self.working_directory else None

        try:
            result = subprocess.run(
                input,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**subprocess.os.environ, **env},
                cwd=cwd,
            )
            output = result.stdout + result.stderr
            exit_code = result.returncode
        except subprocess.TimeoutExpired as e:
            output = f"Command timed out after {timeout}s"
            exit_code = -1
            if check == "raise":
                raise RuntimeError(f"{error_msg}: {output}") from e
        except Exception as e:
            output = str(e)
            exit_code = -1
            if check == "raise":
                raise RuntimeError(f"{error_msg}: {output}") from e

        logger.debug("Output: %s", output)

        if check != "ignore" and exit_code != 0:
            msg = f"Command {input!r} failed ({exit_code=}): {error_msg}"
            logger.error(msg)
            if check == "raise":
                self.close()
                raise RuntimeError(msg)

        return output

    def read_file(
        self,
        path: str | PurePath,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        """Read file contents.

        Args:
            path: Path to file
            encoding: File encoding
            errors: Error handling mode

        Returns:
            File contents
        """
        p = Path(path)
        return p.read_text(encoding=encoding, errors=errors)

    def write_file(self, path: str | PurePath, content: str) -> None:
        """Write content to file.

        Args:
            path: Path to file
            content: Content to write
        """
        p = Path(path)
        p.write_text(content)

    def set_env_variables(self, env_variables: dict[str, str]) -> None:
        """Set environment variables.

        Args:
            env_variables: Variables to set
        """
        if not env_variables:
            logger.debug("No environment variables to set")
            return
        self._env_variables.update(env_variables)
        _env_setters = [f"export {k}={shlex.quote(str(v))}" for k, v in env_variables.items()]
        command = " && ".join(_env_setters)
        self.communicate(command, check="raise")

    def execute_command(
        self,
        command: str,
        shell: bool = True,
        check: bool = False,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> subprocess.CompletedProcess:
        """Execute a command independent of the session.

        Args:
            command: Command to run
            shell: Use shell execution
            check: Raise on non-zero exit
            env: Additional environment variables
            cwd: Working directory

        Returns:
            CompletedProcess result
        """
        full_env = {**subprocess.os.environ, **self._env_variables}
        if env:
            full_env.update(env)
        return subprocess.run(
            command if shell else shlex.split(command),
            shell=shell,
            check=check,
            env=full_env,
            cwd=cwd,
            capture_output=True,
            text=True,
        )

    @property
    def is_started(self) -> bool:
        """Check if environment has been started."""
        return self._started
