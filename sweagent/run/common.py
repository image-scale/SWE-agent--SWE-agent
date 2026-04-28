from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class BasicCLI:
    """Basic CLI parser using simple-parsing."""

    def __init__(self, config_class: type[T]):
        self.config_class = config_class

    def get_config(self, args: list[str]) -> T:
        raise NotImplementedError
