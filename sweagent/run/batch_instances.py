from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel
from swerex.deployment.config import DockerDeploymentConfig

from sweagent.agent.problem_statement import ProblemStatement, TextProblemStatement
from sweagent.environment.repo import PreExistingRepoConfig, SWESmithRepoConfig
from sweagent.environment.swe_env import EnvironmentConfig


class BatchInstance(BaseModel):
    """A batch instance for running."""

    env: EnvironmentConfig
    problem_statement: ProblemStatement

    class Config:
        arbitrary_types_allowed = True


class SimpleBatchInstance(BaseModel):
    """A simple batch instance."""

    image_name: str
    problem_statement: str
    id: str = ""

    @classmethod
    def from_swe_bench(cls, data: dict[str, Any]) -> "SimpleBatchInstance":
        raise NotImplementedError

    def to_full_batch_instance(self, deployment: DockerDeploymentConfig) -> BatchInstance:
        raise NotImplementedError


class InstancesConfig(BaseModel):
    """Base configuration for instances."""

    path: Path | None = None
    filter: str = ""
    slice: str = ""


class SWEBenchInstances(InstancesConfig):
    """Configuration for SWE-bench instances."""

    subset: str = "lite"
    split: str = "test"

    def get_instance_configs(self) -> list[BatchInstance]:
        raise NotImplementedError


class SWESmithInstances(InstancesConfig):
    """Configuration for SWE-smith instances."""

    def get_instance_configs(self) -> list[BatchInstance]:
        raise NotImplementedError


def _slice_spec_to_slice(spec: str) -> slice:
    """Convert a slice specification string to a slice object."""
    raise NotImplementedError
