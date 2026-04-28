from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


def main(args: list[str] | None = None) -> int:
    """Main entry point for the SWE-agent CLI."""
    parser = argparse.ArgumentParser(
        prog="sweagent",
        description="SWE-agent: A tool for autonomous software engineering",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run subcommand
    run_parser = subparsers.add_parser("run", help="Run the agent on a task")
    run_parser.add_argument("--config", type=str, help="Path to config file")

    # run-batch subcommand
    batch_parser = subparsers.add_parser("run-batch", help="Run the agent on a batch of tasks")
    batch_parser.add_argument("--config", type=str, help="Path to config file")

    # run-replay subcommand
    replay_parser = subparsers.add_parser(
        "run-replay",
        help="Replay a trajectory file",
        description="Replay a trajectory file to reproduce agent actions",
    )
    replay_parser.add_argument("--config", type=str, help="Path to config file")

    # Parse known args to handle dotted arguments
    parsed_args, remaining = parser.parse_known_args(args)

    # Show help if no command is given
    if not parsed_args.command:
        parser.print_help()
        return 1

    # Parse dotted arguments from remaining
    dotted_args = _parse_dotted_args(remaining)

    # Handle subcommands
    if parsed_args.command == "run":
        return run_command(parsed_args, dotted_args)
    elif parsed_args.command == "run-batch":
        return run_batch_command(parsed_args, dotted_args)
    elif parsed_args.command == "run-replay":
        return run_replay_command(parsed_args, dotted_args)

    return 0


def _parse_dotted_args(args: list[str]) -> dict[str, Any]:
    """Parse dotted arguments like --agent.model.name value."""
    result: dict[str, Any] = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key = arg[2:]  # Remove --
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                value = args[i + 1]
                # Try to convert to appropriate type
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                elif value.isdigit():
                    value = int(value)
                _set_nested_key(result, key, value)
                i += 2
            else:
                _set_nested_key(result, key, True)
                i += 1
        else:
            i += 1
    return result


def _set_nested_key(d: dict, key: str, value: Any) -> None:
    """Set a nested dictionary key from dotted notation."""
    parts = key.split(".")
    for part in parts[:-1]:
        if part not in d:
            d[part] = {}
        d = d[part]
    d[parts[-1]] = value


def run_command(args: argparse.Namespace, dotted_args: dict[str, Any]) -> int:
    """Execute the run command."""
    # Placeholder for now
    print("Running agent...")
    return 0


def run_batch_command(args: argparse.Namespace, dotted_args: dict[str, Any]) -> int:
    """Execute the run-batch command."""
    # Get instances configuration
    instances_config = dotted_args.get("instances", {})
    instances_path = instances_config.get("path")
    instances_filter = instances_config.get("filter", "")
    instances_type = instances_config.get("type", "simple_file")
    raise_exceptions = dotted_args.get("raise_exceptions", False)

    if not instances_path:
        print("No instances path provided")
        return 1

    # Load instances from path
    instances_path = Path(instances_path)
    if not instances_path.exists():
        print(f"Instances file not found: {instances_path}")
        return 1

    # Load the instances file
    with open(instances_path) as f:
        if instances_path.suffix in [".yaml", ".yml"]:
            instances_data = yaml.safe_load(f)
        else:
            import json
            instances_data = json.load(f)

    # Handle different instance types
    if isinstance(instances_data, dict):
        instances_list = instances_data.get("instances", [])
    else:
        instances_list = instances_data

    # Apply filter
    if instances_filter:
        pattern = re.compile(instances_filter)
        instances_list = [
            inst for inst in instances_list
            if pattern.match(inst.get("instance_id", "") or inst.get("id", ""))
        ]

    # Check if empty
    if not instances_list:
        if raise_exceptions:
            msg = "No instances to run"
            raise ValueError(msg)
        print("No instances to run")
        return 1

    print(f"Running batch with {len(instances_list)} instances...")
    return 0


def run_replay_command(args: argparse.Namespace, dotted_args: dict[str, Any]) -> int:
    """Execute the run-replay command."""
    # Placeholder for now
    print("Running replay...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
