"""Repository configuration types."""

import os
import shlex
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Repo(Protocol):
    """Protocol for repository configurations."""

    base_commit: str
    repo_name: str

    def copy(self, deployment: Any) -> None:
        """Copy the repository to the deployment."""
        ...

    def get_reset_commands(self) -> list[str]:
        """Get commands to reset the repository to base state."""
        ...


def _get_git_reset_commands(base_commit: str) -> list[str]:
    """Get standard git commands to reset to a commit."""
    return [
        "git fetch",
        "git status",
        "git restore .",
        "git reset --hard",
        f"git checkout {shlex.quote(base_commit)}",
        "git clean -fdq",
    ]


class PreExistingRepoConfig(BaseModel):
    """Configuration for a repository that already exists on the deployment.

    Use this when the repository is already present and doesn't need to be copied.
    """

    repo_name: str
    """The repo name (the repository must be located at the root of the deployment)."""

    base_commit: str = Field(default="HEAD")
    """The commit to reset the repository to."""

    type: Literal["preexisting"] = "preexisting"
    """Discriminator for (de)serialization/CLI."""

    reset: bool = True
    """If True, reset the repository to the base commit after the copy operation."""

    model_config = ConfigDict(extra="forbid")

    def copy(self, deployment: Any) -> None:
        """Does nothing since repo already exists."""
        pass

    def get_reset_commands(self) -> list[str]:
        """Get commands issued after copy or when environment is reset."""
        if self.reset:
            return _get_git_reset_commands(self.base_commit)
        return []


class LocalRepoConfig(BaseModel):
    """Configuration for a local repository to be copied to the deployment."""

    path: Path
    """Local path to the repository."""

    base_commit: str = Field(default="HEAD")
    """The commit to reset the repository to."""

    type: Literal["local"] = "local"
    """Discriminator for (de)serialization/CLI."""

    model_config = ConfigDict(extra="forbid")

    @property
    def repo_name(self) -> str:
        """Get the repository name from the path."""
        return Path(self.path).resolve().name.replace(" ", "-").replace("'", "")

    def check_valid_repo(self) -> "LocalRepoConfig":
        """Validate that the path is a git repository."""
        git_dir = self.path / ".git"
        if not git_dir.exists():
            parent_check = self.path
            found = False
            while parent_check.parent != parent_check:
                if (parent_check / ".git").exists():
                    found = True
                    break
                parent_check = parent_check.parent
            if not found:
                msg = f"Could not find git repository at {self.path=}."
                raise ValueError(msg)
        return self

    def copy(self, deployment: Any) -> None:
        """Copy the repository to the deployment."""
        self.check_valid_repo()
        if hasattr(deployment, "upload"):
            deployment.upload(str(self.path), f"/{self.repo_name}")

    def get_reset_commands(self) -> list[str]:
        """Get commands issued after copy or when environment is reset."""
        return _get_git_reset_commands(self.base_commit)


class GithubRepoConfig(BaseModel):
    """Configuration for a GitHub repository to be cloned."""

    github_url: str
    """GitHub URL or shorthand (owner/repo)."""

    base_commit: str = Field(default="HEAD")
    """The commit to reset the repository to."""

    clone_timeout: float = 500
    """Timeout for git clone operation."""

    type: Literal["github"] = "github"
    """Discriminator for (de)serialization/CLI."""

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        """Expand shorthand URLs to full GitHub URLs."""
        if self.github_url.count("/") == 1 and not self.github_url.startswith("http"):
            object.__setattr__(self, "github_url", f"https://github.com/{self.github_url}")

    @property
    def repo_name(self) -> str:
        """Get the repository name from the URL."""
        url = self.github_url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        parts = url.split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}__{parts[-1]}"
        return parts[-1]

    def _get_url_with_token(self, token: str) -> str:
        """Prepend github token to URL."""
        if not token:
            return self.github_url
        if "@" in self.github_url:
            return self.github_url
        _, _, url_no_protocol = self.github_url.partition("://")
        return f"https://{token}@{url_no_protocol}"

    def copy(self, deployment: Any) -> None:
        """Clone the repository to the deployment."""
        github_token = os.getenv("GITHUB_TOKEN", "")
        url = self._get_url_with_token(github_token)
        commands = [
            f"mkdir /{self.repo_name}",
            f"cd /{self.repo_name}",
            "git init",
            f"git remote add origin {shlex.quote(url)}",
            f"git fetch --depth 1 origin {shlex.quote(self.base_commit)}",
            "git checkout FETCH_HEAD",
            "cd ..",
        ]
        if hasattr(deployment, "execute"):
            deployment.execute(" && ".join(commands), timeout=self.clone_timeout)

    def get_reset_commands(self) -> list[str]:
        """Get commands issued after copy or when environment is reset."""
        return _get_git_reset_commands(self.base_commit)


RepoConfig = LocalRepoConfig | GithubRepoConfig | PreExistingRepoConfig


def repo_from_simplified_input(
    *,
    input: str,
    base_commit: str = "HEAD",
    type: Literal["local", "github", "preexisting", "auto"] = "auto",
) -> RepoConfig:
    """Get repo config from a simplified input.

    Args:
        input: Local path or GitHub URL
        base_commit: Commit to start from
        type: The type of repo. Set to "auto" to automatically detect the type
            (does not work for preexisting repos).

    Returns:
        Appropriate RepoConfig instance
    """
    if type == "local":
        return LocalRepoConfig(path=Path(input), base_commit=base_commit)
    if type == "github":
        return GithubRepoConfig(github_url=input, base_commit=base_commit)
    if type == "preexisting":
        return PreExistingRepoConfig(repo_name=input, base_commit=base_commit)
    if type == "auto":
        if input.startswith("https://github.com/") or input.startswith("http://github.com/"):
            return GithubRepoConfig(github_url=input, base_commit=base_commit)
        else:
            return LocalRepoConfig(path=Path(input), base_commit=base_commit)
    msg = f"Unknown repo type: {type}"
    raise ValueError(msg)
