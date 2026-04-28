from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests
from pydantic import BaseModel

from sweagent.agent.problem_statement import GithubIssue, ProblemStatement
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

        # If data_path is present but not a valid GitHub URL, fail
        data_path = info.get("data_path", "")
        if data_path:
            # Check if it's a valid URL
            try:
                parsed = urlparse(data_path)
                if not parsed.scheme or not parsed.netloc:
                    return False
            except Exception:
                return False

        # Check GitHub issue status if problem_statement is a GitHub issue
        if isinstance(self._problem_statement, GithubIssue):
            issue_url = self._problem_statement.github_url
            issue_info = self._get_issue_info(issue_url)
            if issue_info is None:
                # Can't verify issue status, don't open PR
                return False
            # Check if issue is closed
            if issue_info.get("state") == "closed":
                return False
            # Check if issue is assigned
            if issue_info.get("assignees"):
                return False
            # Check if issue is locked
            if issue_info.get("locked"):
                return False
            # Check if issue already has commits/PRs referencing it
            if self._config.skip_if_commits_reference_issue:
                if self._has_linked_pr(issue_url, issue_info):
                    return False

        return True

    def _get_issue_info(self, issue_url: str) -> dict[str, Any] | None:
        """Get issue info from GitHub API."""
        # Parse the issue URL to get owner, repo, issue number
        # Format: https://github.com/owner/repo/issues/123
        match = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", issue_url)
        if not match:
            return None

        owner, repo, issue_num = match.groups()
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_num}"

        headers = {}
        if self._token:
            headers["Authorization"] = f"token {self._token}"

        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass

        return None

    def _has_linked_pr(self, issue_url: str, issue_info: dict[str, Any]) -> bool:
        """Check if issue has a linked PR via timeline events."""
        # Parse the issue URL
        match = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", issue_url)
        if not match:
            return False

        owner, repo, issue_num = match.groups()
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_num}/timeline"

        headers = {"Accept": "application/vnd.github.mockingbird-preview+json"}
        if self._token:
            headers["Authorization"] = f"token {self._token}"

        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                events = response.json()
                for event in events:
                    # Check for cross-referenced PRs or commits
                    if event.get("event") == "cross-referenced":
                        source = event.get("source", {})
                        if source.get("type") == "issue":
                            issue = source.get("issue", {})
                            if issue.get("pull_request"):
                                return True
        except requests.RequestException:
            pass

        return False


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
