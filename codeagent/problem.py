"""Problem statement types for defining tasks.

This module provides various types of problem statements that describe
the task an agent should work on. Problem statements can come from
text, files, or other sources.
"""

import hashlib
import uuid
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ProblemStatement(Protocol):
    """Protocol for problem statements.

    Any class implementing this protocol can be used as a problem statement
    for the agent.
    """

    id: str

    def get_problem_statement(self) -> str:
        """Return the problem statement text."""
        ...

    def get_problem_statement_for_env(self) -> str:
        """Return problem statement for environment variables.

        By default returns the same as get_problem_statement().
        """
        return self.get_problem_statement()

    def get_extra_fields(self) -> dict[str, Any]:
        """Return extra fields for template rendering."""
        ...


class BaseProblemStatement(BaseModel):
    """Base class for built-in problem statement types."""

    def get_problem_statement(self) -> str:
        """Return the problem statement text."""
        raise NotImplementedError

    def get_problem_statement_for_env(self) -> str:
        """Return problem statement for environment variables."""
        return self.get_problem_statement()

    def get_extra_fields(self) -> dict[str, Any]:
        """Return extra fields for template rendering."""
        return {}


class EmptyProblemStatement(BaseProblemStatement):
    """A problem statement with no content.

    Useful when the task is defined elsewhere or when testing.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["empty"] = "empty"

    model_config = ConfigDict(extra="forbid")

    def get_problem_statement(self) -> str:
        """Return empty string."""
        return ""


class TextProblemStatement(BaseProblemStatement):
    """A problem statement defined by inline text.

    The ID is automatically generated from a hash of the text content.
    """

    text: str
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    type: Literal["text"] = "text"
    id: str | None = None

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        """Generate ID from text hash if not provided."""
        if self.id is None:
            self.id = hashlib.sha256(self.text.encode()).hexdigest()[:6]

    def get_problem_statement(self) -> str:
        """Return the text content."""
        return self.text

    def get_extra_fields(self) -> dict[str, Any]:
        """Return configured extra fields."""
        return self.extra_fields

    def __repr__(self) -> str:
        preview = self.text[:30] + "..." if len(self.text) > 30 else self.text
        return f"TextProblemStatement(id={self.id}, text={preview})"


class FileProblemStatement(BaseProblemStatement):
    """A problem statement loaded from a file.

    The ID is automatically generated from a hash of the file content.
    """

    path: Path
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    type: Literal["text_file"] = "text_file"
    id: str | None = None

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        """Generate ID from file content hash if not provided."""
        if self.id is None:
            self.id = hashlib.sha256(self.get_problem_statement().encode()).hexdigest()[:6]

    def get_problem_statement(self) -> str:
        """Read and return the file content."""
        return self.path.read_text()

    def get_extra_fields(self) -> dict[str, Any]:
        """Return configured extra fields."""
        return self.extra_fields
