from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from swerex.deployment.config import DockerDeploymentConfig

from sweagent.agent.problem_statement import ProblemStatement, TextProblemStatement
from sweagent.environment.repo import PreExistingRepoConfig, SWESmithRepoConfig
from sweagent.environment.swe_env import EnvironmentConfig
from sweagent.utils.github import _is_repo_private


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
        """Create a SimpleBatchInstance from SWE-bench data."""
        instance_id = data.get("instance_id", "")
        repo = data.get("repo", "").replace("/", "__")
        version = data.get("version", "")

        # Construct image name following SWE-bench convention
        image_name = f"docker.io/swebench/sweb.eval.x86_64.{repo}_{version.replace('.', '_')}_{instance_id.split('-')[0]}:latest"

        # Get problem statement
        problem_statement = data.get("problem_statement", "")

        return cls(
            image_name=image_name,
            problem_statement=problem_statement,
            id=instance_id,
        )

    def to_full_batch_instance(self, deployment: DockerDeploymentConfig) -> BatchInstance:
        """Convert to a full BatchInstance."""
        # Override the image in deployment
        new_deployment = DockerDeploymentConfig(image=self.image_name)

        env_config = EnvironmentConfig(
            deployment=new_deployment,
            repo=PreExistingRepoConfig(repo_name="testbed"),
        )

        problem = TextProblemStatement(text=self.problem_statement, id=self.id)

        return BatchInstance(
            env=env_config,
            problem_statement=problem,
        )


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
        """Get instance configurations from the instances file."""
        if not self.path:
            msg = "Path is required"
            raise ValueError(msg)

        with open(self.path) as f:
            instances_data = json.load(f)

        # Apply filter
        if self.filter:
            pattern = re.compile(self.filter)
            instances_data = [
                inst for inst in instances_data
                if pattern.match(inst.get("instance_id", ""))
            ]

        # Apply slice
        if self.slice:
            s = _slice_spec_to_slice(self.slice)
            instances_data = instances_data[s]

        instances: list[BatchInstance] = []

        for inst_data in instances_data:
            instance_id = inst_data.get("instance_id", "")
            image_name = inst_data.get("image_name", "")
            repo = inst_data.get("repo", "")
            problem_statement = inst_data.get("problem_statement", "")

            # Determine if repo is private
            token = os.environ.get("GITHUB_TOKEN", "")
            is_private = _is_repo_private(repo, token)

            # Build mirror URL if private
            mirror_url = ""
            if is_private:
                if not token:
                    msg = "GITHUB_TOKEN is not set but repository is private"
                    raise ValueError(msg)
                mirror_url = f"https://github.com/{repo}.git"

            # Extract base_commit from instance_id
            # Format: org__repo.commit__test_N
            parts = instance_id.split(".")
            base_commit = parts[1].split("__")[0] if len(parts) > 1 else ""

            repo_config = SWESmithRepoConfig(
                repo_name="testbed",
                base_commit=base_commit,
                mirror_url=mirror_url,
            )

            env_config = EnvironmentConfig(
                deployment=DockerDeploymentConfig(image=image_name),
                repo=repo_config,
            )

            problem = TextProblemStatement(text=problem_statement, id=instance_id)

            instances.append(BatchInstance(
                env=env_config,
                problem_statement=problem,
            ))

        return instances


def _slice_spec_to_slice(spec: str) -> slice:
    """Convert a slice specification string to a slice object.

    Examples:
        "10" -> slice(10)
        "10:20" -> slice(10, 20)
        "10:20:3" -> slice(10, 20, 3)
    """
    parts = spec.split(":")

    if len(parts) == 1:
        return slice(int(parts[0]))
    elif len(parts) == 2:
        start = int(parts[0]) if parts[0] else None
        stop = int(parts[1]) if parts[1] else None
        return slice(start, stop)
    elif len(parts) == 3:
        start = int(parts[0]) if parts[0] else None
        stop = int(parts[1]) if parts[1] else None
        step = int(parts[2]) if parts[2] else None
        return slice(start, stop, step)
    else:
        msg = f"Invalid slice specification: {spec}"
        raise ValueError(msg)
