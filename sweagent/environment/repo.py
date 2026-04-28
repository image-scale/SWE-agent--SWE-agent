from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class RepoConfig(BaseModel):
    """Base configuration for repositories."""

    repo_name: str = ""

    def get_reset_commands(self) -> list[str]:
        return []


class LocalRepoConfig(RepoConfig):
    """Configuration for a local repository."""

    path: Path


class PreExistingRepoConfig(RepoConfig):
    """Configuration for a pre-existing repository in a container."""

    repo_name: str = "testbed"


class GithubRepoConfig(RepoConfig):
    """Configuration for a GitHub repository."""

    github_url: str


class SWESmithRepoConfig(RepoConfig):
    """Configuration for SWE-smith repository."""

    repo_name: str = "testbed"
    base_commit: str = ""
    mirror_url: str = ""

    def get_reset_commands(self) -> list[str]:
        """Get commands to reset the repository to the base commit."""
        if self.mirror_url:
            # Fetch from mirror URL
            token = os.environ.get("GITHUB_TOKEN", "")
            fetch_url = self._get_url_with_token(self.mirror_url, token)
            return [
                f"git fetch {fetch_url} {self.base_commit}",
                "git checkout FETCH_HEAD",
            ]
        else:
            # Standard reset to base commit
            return [
                "git fetch",
                f"git checkout {self.base_commit}",
            ]

    @staticmethod
    def _get_url_with_token(url: str, token: str) -> str:
        """Embed token into URL for authentication."""
        if not url:
            return ""
        if not token:
            return url
        # Insert token after https://
        # e.g., https://github.com/... -> https://TOKEN@github.com/...
        if url.startswith("https://"):
            return url.replace("https://", f"https://{token}@", 1)
        return url
