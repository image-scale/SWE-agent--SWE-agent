from __future__ import annotations


class InvalidGithubURL(Exception):
    """Exception raised when a GitHub URL is invalid."""
    pass


_repo_privacy_cache: dict[str, bool] = {}


def _is_github_repo_url(url: str) -> bool:
    """Check if a URL is a GitHub repository URL."""
    raise NotImplementedError


def _parse_gh_repo_url(url: str) -> tuple[str, str]:
    """Parse a GitHub repository URL and return (owner, repo)."""
    raise NotImplementedError


def _is_github_issue_url(url: str) -> bool:
    """Check if a URL is a GitHub issue URL."""
    raise NotImplementedError


def _parse_gh_issue_url(url: str) -> tuple[str, str, str]:
    """Parse a GitHub issue URL and return (owner, repo, issue_number)."""
    raise NotImplementedError


def _get_associated_commit_urls(org: str, repo: str, issue_number: str, token: str) -> list[str]:
    """Get commit URLs associated with an issue."""
    raise NotImplementedError


def _is_repo_private(repo_full_name: str, token: str) -> bool:
    """Check if a repository is private."""
    raise NotImplementedError
