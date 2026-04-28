from __future__ import annotations

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
        raise NotImplementedError

    @staticmethod
    def _get_url_with_token(url: str, token: str) -> str:
        raise NotImplementedError
