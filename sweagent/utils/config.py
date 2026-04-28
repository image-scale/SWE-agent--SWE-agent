from __future__ import annotations

from pathlib import Path

from sweagent import REPO_ROOT


def _convert_path_to_abspath(path: str | Path) -> Path:
    """Convert a path to absolute path, using REPO_ROOT as base for relative paths."""
    p = Path(path)
    if p.is_absolute():
        return p
    return REPO_ROOT / p


def _convert_paths_to_abspath(paths: list[Path]) -> list[Path]:
    """Convert a list of paths to absolute paths."""
    return [_convert_path_to_abspath(p) for p in paths]
