from __future__ import annotations


class EnvHook:
    """Base class for environment hooks."""

    def on_start(self) -> None:
        pass

    def on_close(self) -> None:
        pass

    def on_reset(self) -> None:
        pass
