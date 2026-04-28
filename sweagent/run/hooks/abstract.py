from __future__ import annotations

from sweagent.agent.problem_statement import ProblemStatement
from sweagent.environment.swe_env import SWEEnv
from sweagent.types import AgentRunResult


class RunHook:
    """Base class for run hooks."""

    def on_instance_start(
        self,
        index: int,
        env: SWEEnv,
        problem_statement: ProblemStatement,
    ) -> None:
        pass

    def on_instance_completed(self, result: AgentRunResult) -> None:
        pass
