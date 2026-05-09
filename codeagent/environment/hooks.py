"""Environment lifecycle hooks."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from codeagent.environment.repo import Repo, RepoConfig
    from codeagent.environment.swe_env import SWEEnv


class EnvHook:
    """Hook to be used in SWEEnv.

    Subclass this class, add functionality and add it with SWEEnv.add_hook(hook).
    This allows injecting custom functionality at different stages of the environment
    lifecycle, in particular to connect the agent to a new interface (like a GUI).
    """

    def on_init(self, *, env: "SWEEnv") -> None:
        """Gets called when the hook is added."""
        pass

    def on_copy_repo_started(self, repo: "RepoConfig | Repo") -> None:
        """Gets called when the repository is being cloned to the container."""
        pass

    def on_start_deployment(self) -> None:
        """Gets called when the deployment is being started."""
        pass

    def on_install_env_started(self) -> None:
        """Called when we start installing the environment."""
        pass

    def on_close(self) -> None:
        """Called when the environment is closed."""
        pass

    def on_environment_startup(self) -> None:
        """Called when the environment is started."""
        pass


class CombinedEnvHooks(EnvHook):
    """Aggregates multiple hooks and calls them in order."""

    def __init__(self) -> None:
        self._hooks: list[EnvHook] = []

    def add_hook(self, hook: EnvHook) -> None:
        """Add a hook to the list."""
        self._hooks.append(hook)

    def on_init(self, *, env: "SWEEnv") -> None:
        for hook in self._hooks:
            hook.on_init(env=env)

    def on_copy_repo_started(self, repo: "RepoConfig | Repo") -> None:
        for hook in self._hooks:
            hook.on_copy_repo_started(repo=repo)

    def on_start_deployment(self) -> None:
        for hook in self._hooks:
            hook.on_start_deployment()

    def on_install_env_started(self) -> None:
        for hook in self._hooks:
            hook.on_install_env_started()

    def on_close(self) -> None:
        for hook in self._hooks:
            hook.on_close()

    def on_environment_startup(self) -> None:
        for hook in self._hooks:
            hook.on_environment_startup()
