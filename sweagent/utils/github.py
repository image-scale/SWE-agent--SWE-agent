from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


class InvalidGithubURL(Exception):
    """Exception raised when a GitHub URL is invalid."""
    pass


_repo_privacy_cache: dict[str, bool] = {}


def _is_github_repo_url(url: str) -> bool:
    """Check if a URL is a GitHub repository URL."""
    if not url:
        return False
    # Check for github.com with at least owner/repo
    pattern = r"(^https?://)?github\.com/[^/]+/[^/]+"
    return bool(re.match(pattern, url))


def _parse_gh_repo_url(url: str) -> tuple[str, str]:
    """Parse a GitHub repository URL and return (owner, repo)."""
    # Handle various formats:
    # https://github.com/owner/repo
    # github.com/owner/repo
    # git@github.com/owner/repo
    # github.com/owner/repo/anything

    # Remove protocol prefix
    url = re.sub(r"^(https?://|git@)", "", url)

    # Check it starts with github.com
    if not url.startswith("github.com/"):
        raise InvalidGithubURL(f"Invalid GitHub URL: {url}")

    # Remove github.com/
    path = url[len("github.com/"):]

    # Split by /
    parts = path.split("/")

    # Filter out empty parts
    parts = [p for p in parts if p]

    if len(parts) < 2:
        raise InvalidGithubURL(f"Invalid GitHub URL: {url}")

    owner = parts[0]
    repo = parts[1]

    # Remove .git suffix if present
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:
        raise InvalidGithubURL(f"Invalid GitHub URL: {url}")

    return (owner, repo)


def _is_github_issue_url(url: str) -> bool:
    """Check if a URL is a GitHub issue URL."""
    if not url:
        return False
    # Match pattern: github.com/owner/repo/issues/number
    pattern = r"(https?://)?github\.com/[^/]+/[^/]+/issues/\d+"
    return bool(re.match(pattern, url))


def _parse_gh_issue_url(url: str) -> tuple[str, str, str]:
    """Parse a GitHub issue URL and return (owner, repo, issue_number)."""
    # Pattern: github.com/owner/repo/issues/number
    pattern = r"(https?://)?github\.com/([^/]+)/([^/]+)/issues/(\d+)"
    match = re.match(pattern, url)

    if not match:
        raise InvalidGithubURL(f"Invalid GitHub issue URL: {url}")

    owner = match.group(2)
    repo = match.group(3)
    issue_number = match.group(4)

    return (owner, repo, issue_number)


def _get_associated_commit_urls(org: str, repo: str, issue_number: str, token: str) -> list[str]:
    """Get commit URLs associated with an issue."""
    # This uses the GitHub API to find commits that reference the issue
    # For simplicity, we look at the timeline events
    url = f"https://api.github.com/repos/{org}/{repo}/issues/{issue_number}/timeline"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError:
        return []

    commit_urls = []
    for event in data:
        if event.get("event") == "referenced" and "commit_url" in event:
            commit_urls.append(event["commit_url"])
        if event.get("event") == "committed":
            sha = event.get("sha", "")
            if sha:
                commit_urls.append(f"https://github.com/{org}/{repo}/commit/{sha}")

    return commit_urls


def _is_repo_private(repo_full_name: str, token: str) -> bool:
    """Check if a repository is private."""
    if repo_full_name in _repo_privacy_cache:
        return _repo_privacy_cache[repo_full_name]

    url = f"https://api.github.com/repos/{repo_full_name}"

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            data = json.loads(response.read().decode())
            is_private = data.get("private", False)
            _repo_privacy_cache[repo_full_name] = is_private
            return is_private
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # If we get 404, assume private (can't access = likely private)
            _repo_privacy_cache[repo_full_name] = True
            return True
        raise
