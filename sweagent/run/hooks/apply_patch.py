from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from sweagent.agent.problem_statement import ProblemStatement
from sweagent.environment.swe_env import SWEEnv
from sweagent.run.hooks.abstract import RunHook
from sweagent.types import AgentRunResult


class SaveApplyPatchHook(RunHook):
    """Hook to save and apply patches."""

    def __init__(self, show_success_message: bool = True):
        self.show_success_message = show_success_message
        self._output_dir: Path | None = None
        self._local = threading.local()

    def on_instance_start(
        self,
        index: int,
        env: SWEEnv,
        problem_statement: ProblemStatement,
    ) -> None:
        raise NotImplementedError

    def on_instance_completed(self, result: AgentRunResult) -> None:
        raise NotImplementedError
