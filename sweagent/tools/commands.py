from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel


class Argument(BaseModel):
    """Represents a command argument."""

    name: str
    type: str
    description: str
    required: bool = True
    enum: list[str] | None = None
    argument_format: str | None = None


class Command(BaseModel):
    """Represents a tool command."""

    name: str
    docstring: str
    signature: str | None = None
    arguments: list[Argument] = []
    end_name: str | None = None

    def model_post_init(self, __context: Any) -> None:
        raise NotImplementedError

    @property
    def invoke_format(self) -> str:
        raise NotImplementedError

    def get_function_calling_tool(self) -> dict[str, Any]:
        raise NotImplementedError
