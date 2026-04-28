from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def quick_stats(directory: str | Path) -> str:
    """Get quick statistics from trajectory files in a directory."""
    directory = Path(directory)

    # Find all .traj files recursively
    traj_files = list(directory.rglob("*.traj"))

    if not traj_files:
        return "No .traj files found."

    # Collect statistics by exit status
    stats_by_exit_status: dict[str, list[dict]] = defaultdict(list)

    for traj_file in traj_files:
        try:
            with open(traj_file) as f:
                data = json.load(f)

            info = data.get("info", {})
            exit_status = info.get("exit_status", "unknown")

            stats_by_exit_status[exit_status].append({
                "file": str(traj_file),
                "api_calls": info.get("model_stats", {}).get("api_calls", 0),
            })
        except (json.JSONDecodeError, KeyError, TypeError):
            stats_by_exit_status["error"].append({
                "file": str(traj_file),
                "api_calls": 0,
            })

    # Format the output
    lines = []
    for exit_status, trajs in sorted(stats_by_exit_status.items()):
        lines.append(f"## `{exit_status}`")
        lines.append(f"  Count: {len(trajs)}")
        total_api_calls = sum(t["api_calls"] for t in trajs)
        lines.append(f"  Total API calls: {total_api_calls}")
        lines.append("")

    return "\n".join(lines)
