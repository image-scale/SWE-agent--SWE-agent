from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class Bundle(BaseModel):
    """Represents a bundle of tools."""

    path: Path
    hidden_tools: list[str] = []
