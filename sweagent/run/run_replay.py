from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
from swerex.deployment.config import DeploymentConfig


class RunReplayConfig(BaseModel):
    """Configuration for replaying a trajectory."""

    traj_path: Path
    deployment: DeploymentConfig
    output_dir: Path | None = None

    class Config:
        arbitrary_types_allowed = True


class RunReplay:
    """Replay a trajectory."""

    def __init__(self, config: RunReplayConfig, _catch_errors: bool = True, _require_zero_exit_code: bool = False):
        self.config = config
        self._catch_errors = _catch_errors
        self._require_zero_exit_code = _require_zero_exit_code

    @classmethod
    def from_config(
        cls,
        config: RunReplayConfig,
        _catch_errors: bool = True,
        _require_zero_exit_code: bool = False,
    ) -> "RunReplay":
        raise NotImplementedError

    def main(self) -> Any:
        raise NotImplementedError
