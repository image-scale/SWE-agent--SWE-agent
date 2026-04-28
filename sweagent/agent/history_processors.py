from __future__ import annotations

from typing import Any

from sweagent.types import History


ELIDED_OBSERVATION_MESSAGE = "[Old environment output was trimmed. Get the most recent environment state by running a command.]"


class HistoryProcessor:
    """Base class for history processors."""

    def __call__(self, history: History) -> History:
        raise NotImplementedError


class LastNObservations(HistoryProcessor):
    """Keep only the last N observations."""

    def __init__(self, n: int = 3):
        self.n = n

    def __call__(self, history: History) -> History:
        """Process history to keep only the last N observations.

        Replaces older observations with a placeholder message.
        Keeps the first observation (instance template) intact.
        """
        # Find all observation indices
        observation_indices = []
        for i, entry in enumerate(history):
            if entry.get("message_type") == "observation":
                observation_indices.append(i)

        # Keep the first observation (instance template) and last N
        if len(observation_indices) <= self.n + 1:
            return history

        # Indices to elide: all except first and last N
        indices_to_keep = set([observation_indices[0]] + observation_indices[-self.n :])
        indices_to_elide = set(observation_indices) - indices_to_keep

        # Create new history with elided observations
        new_history = History()
        for i, entry in enumerate(history):
            if i in indices_to_elide:
                new_entry = dict(entry)
                new_entry["content"] = ELIDED_OBSERVATION_MESSAGE
                new_history.append(new_entry)
            else:
                new_history.append(entry)

        return new_history


class TagToolCallObservations(HistoryProcessor):
    """Tag observations based on function names."""

    def __init__(self, tags: set[str], function_names: set[str]):
        self.tags = tags
        self.function_names = function_names

    def __call__(self, history: History) -> History:
        """Process history to add tags to entries with matching function names."""
        new_history = History()

        for entry in history:
            action = entry.get("action", "")
            # Check if the action starts with any of the function names
            matches = False
            for func_name in self.function_names:
                if action.startswith(f"{func_name} ") or action == func_name:
                    matches = True
                    break

            if matches:
                new_entry = dict(entry)
                existing_tags = new_entry.get("tags", [])
                if existing_tags is None:
                    existing_tags = []
                new_entry["tags"] = list(set(existing_tags) | self.tags)
                new_history.append(new_entry)
            else:
                new_history.append(entry)

        return new_history
