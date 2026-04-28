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
        """Called when an instance starts processing."""
        # Store in thread-local storage to avoid race conditions
        self._local.problem_statement = problem_statement
        self._local.env = env

    def on_instance_completed(self, result: AgentRunResult) -> None:
        """Called when an instance completes processing."""
        # Get problem statement from thread-local storage
        problem_statement = getattr(self._local, "problem_statement", None)
        if problem_statement is None:
            return

        # Get the submission/patch from the result
        info = result.info or {}
        patch = info.get("submission", "")
        if not patch:
            return

        # Get the instance ID
        instance_id = problem_statement.id
        if not instance_id:
            return

        # Save the patch
        if self._output_dir is not None:
            instance_dir = self._output_dir / instance_id
            instance_dir.mkdir(parents=True, exist_ok=True)
            patch_path = instance_dir / f"{instance_id}.patch"
            patch_path.write_text(patch)
