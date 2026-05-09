"""Agent hooks for lifecycle events."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from codeagent.agent.agent import DefaultAgent


class AgentHook:
    """Hook to be used in DefaultAgent.

    Subclass this class, add functionality and add it with agent.add_hook(hook).
    This allows injecting custom functionality at different stages of the agent
    lifecycle.
    """

    def on_init(self, *, agent: "DefaultAgent") -> None:
        """Gets called when the hook is added."""
        pass

    def on_setup_attempt(self) -> None:
        """Gets called when setting up an attempt."""
        pass

    def on_setup_done(self) -> None:
        """Gets called when setup is complete."""
        pass

    def on_step_start(self) -> None:
        """Gets called at the start of each step."""
        pass

    def on_step_done(self, *, step: Any) -> None:
        """Gets called after a step completes."""
        pass

    def on_query_message_added(self, **kwargs: Any) -> None:
        """Gets called when a message is added to history."""
        pass

    def on_run_start(self) -> None:
        """Gets called when a run starts."""
        pass

    def on_run_done(self, *, result: Any) -> None:
        """Gets called when a run completes."""
        pass

    def on_tools_installation_started(self) -> None:
        """Gets called when tools installation starts."""
        pass


class CombinedAgentHook(AgentHook):
    """Aggregates multiple hooks and calls them in order."""

    def __init__(self) -> None:
        self._hooks: list[AgentHook] = []

    def add_hook(self, hook: AgentHook) -> None:
        """Add a hook to the list."""
        self._hooks.append(hook)

    def on_init(self, *, agent: "DefaultAgent") -> None:
        for hook in self._hooks:
            hook.on_init(agent=agent)

    def on_setup_attempt(self) -> None:
        for hook in self._hooks:
            hook.on_setup_attempt()

    def on_setup_done(self) -> None:
        for hook in self._hooks:
            hook.on_setup_done()

    def on_step_start(self) -> None:
        for hook in self._hooks:
            hook.on_step_start()

    def on_step_done(self, *, step: Any) -> None:
        for hook in self._hooks:
            hook.on_step_done(step=step)

    def on_query_message_added(self, **kwargs: Any) -> None:
        for hook in self._hooks:
            hook.on_query_message_added(**kwargs)

    def on_run_start(self) -> None:
        for hook in self._hooks:
            hook.on_run_start()

    def on_run_done(self, *, result: Any) -> None:
        for hook in self._hooks:
            hook.on_run_done(result=result)

    def on_tools_installation_started(self) -> None:
        for hook in self._hooks:
            hook.on_tools_installation_started()
