from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ProblemStatement:
    """Base class for problem statements."""

    id: str = ""
    type: str = "base"

    def get_problem_statement(self) -> str:
        raise NotImplementedError


class EmptyProblemStatement(ProblemStatement):
    """Empty problem statement."""

    type: str = "empty"

    def get_problem_statement(self) -> str:
        return ""


class TextProblemStatement(BaseModel):
    """Problem statement from plain text."""

    text: str
    id: str = ""
    type: str = "text"

    def get_problem_statement(self) -> str:
        return self.text


class GithubIssue(BaseModel):
    """Problem statement from a GitHub issue."""

    github_url: str
    id: str = ""
    type: str = "github"

    def get_problem_statement(self) -> str:
        raise NotImplementedError


class SWEBenchMultimodalProblemStatement(BaseModel):
    """Multimodal problem statement for SWE-bench."""

    text: str
    issue_images: list[str] = []
    id: str = ""
    type: str = "swe_bench_multimodal"
    _cached_statement: str | None = None

    def get_problem_statement(self) -> str:
        raise NotImplementedError
