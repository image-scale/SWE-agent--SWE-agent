from __future__ import annotations

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
        raise NotImplementedError


def _remove_triple_backticks(text: str) -> str:
    """Remove triple backticks from text."""
    raise NotImplementedError


def format_trajectory_markdown(trajectory: list[dict[str, Any]]) -> str:
    """Format trajectory as markdown."""
    raise NotImplementedError
