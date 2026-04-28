from __future__ import annotations

from pathlib import Path

__version__ = "1.0.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
TOOLS_DIR = REPO_ROOT / "tools"
