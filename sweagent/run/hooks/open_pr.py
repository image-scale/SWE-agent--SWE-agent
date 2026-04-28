from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from sweagent.agent.problem_statement import ProblemStatement
from sweagent.run.hooks.abstract import RunHook
from sweagent.types import AgentRunResult


class OpenPRConfig(BaseModel):
    """Configuration for opening pull requests."""

    skip_if_commits_reference_issue: bool = True


class OpenPRHook(RunHook):
    """Hook to open pull requests."""

    def __init__(self, config: OpenPRConfig | None = None):
        self._config = config or OpenPRConfig()
        self._token: str = ""
        self._problem_statement: ProblemStatement | None = None

    def should_open_pr(self, result: AgentRunResult) -> bool:
        """Determine if a PR should be opened based on the result."""
        # Check if there's a valid submission
        info = result.info or {}

        # Check exit status
        exit_status = info.get("exit_status", "")
        if exit_status != "submitted":
            return False

        # Check if there's a model patch
        model_patch = info.get("submission", "")
        if not model_patch or not model_patch.strip():
            return False

        return True


def _remove_triple_backticks(text: str) -> str:
    """Remove triple backticks from text."""
    return text.replace("```", "")


def format_trajectory_markdown(trajectory: list[dict[str, Any]]) -> str:
    """Format trajectory as markdown."""
    lines = ["<details>", "<summary>Trajectory</summary>", ""]

    for i, step in enumerate(trajectory):
        lines.append(f"### Step {i + 1}")
        lines.append("")

        if "thought" in step and step["thought"]:
            lines.append("**Thought:**")
            lines.append(step["thought"].strip())
            lines.append("")

        if "action" in step and step["action"]:
            lines.append("**Action:**")
            lines.append("```")
            lines.append(step["action"].strip())
            lines.append("```")
            lines.append("")

        if "observation" in step and step["observation"]:
            lines.append("**Observation:**")
            lines.append("```")
            lines.append(step["observation"].strip()[:1000])  # Truncate long outputs
            if len(step["observation"]) > 1000:
                lines.append("... (truncated)")
            lines.append("```")
            lines.append("")

    lines.append("</details>")
    return "\n".join(lines)
