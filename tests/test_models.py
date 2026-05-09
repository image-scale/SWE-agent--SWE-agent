"""Tests for model abstraction layer."""

import json
import pytest
from pathlib import Path

from codeagent.models import (
    InstanceStats,
    ModelConfig,
    ReplayModelConfig,
    PredeterminedModel,
    ReplayModel,
    CostTrackingModel,
    GLOBAL_STATS,
)
from codeagent.exceptions import (
    InstanceCostLimitExceededError,
    TotalCostLimitExceededError,
    InstanceCallLimitExceededError,
)


class TestInstanceStats:
    def test_default_values(self):
        stats = InstanceStats()
        assert stats.instance_cost == 0
        assert stats.tokens_sent == 0
        assert stats.tokens_received == 0
        assert stats.api_calls == 0

    def test_addition(self):
        stats1 = InstanceStats(
            instance_cost=1.0,
            tokens_sent=100,
            tokens_received=50,
            api_calls=2,
        )
        stats2 = InstanceStats(
            instance_cost=0.5,
            tokens_sent=50,
            tokens_received=25,
            api_calls=1,
        )
        result = stats1 + stats2
        assert result.instance_cost == 1.5
        assert result.tokens_sent == 150
        assert result.tokens_received == 75
        assert result.api_calls == 3

    def test_subtraction(self):
        stats1 = InstanceStats(
            instance_cost=1.5,
            tokens_sent=150,
            tokens_received=75,
            api_calls=3,
        )
        stats2 = InstanceStats(
            instance_cost=0.5,
            tokens_sent=50,
            tokens_received=25,
            api_calls=1,
        )
        result = stats1 - stats2
        assert result.instance_cost == 1.0
        assert result.tokens_sent == 100
        assert result.tokens_received == 50
        assert result.api_calls == 2

    def test_addition_does_not_modify_original(self):
        stats1 = InstanceStats(instance_cost=1.0)
        stats2 = InstanceStats(instance_cost=0.5)
        _ = stats1 + stats2
        assert stats1.instance_cost == 1.0
        assert stats2.instance_cost == 0.5


class TestModelConfig:
    def test_default_values(self):
        config = ModelConfig(name="gpt-4")
        assert config.name == "gpt-4"
        assert config.per_instance_cost_limit == 3.0
        assert config.total_cost_limit == 0.0
        assert config.temperature == 0.0
        assert config.top_p == 1.0

    def test_custom_values(self):
        config = ModelConfig(
            name="gpt-4",
            per_instance_cost_limit=5.0,
            temperature=0.7,
            top_p=0.9,
        )
        assert config.per_instance_cost_limit == 5.0
        assert config.temperature == 0.7
        assert config.top_p == 0.9

    def test_id_property(self):
        config = ModelConfig(
            name="gpt-4",
            temperature=0.5,
            top_p=0.9,
            per_instance_cost_limit=2.0,
        )
        model_id = config.id
        assert "gpt-4" in model_id
        assert "t-0.50" in model_id
        assert "p-0.90" in model_id
        assert "c-2.00" in model_id

    def test_id_with_slashes(self):
        config = ModelConfig(name="org/model")
        assert "org--model" in config.id

    def test_id_with_none_top_p(self):
        config = ModelConfig(name="test", top_p=None)
        assert "None" in config.id


class TestPredeterminedModel:
    def test_string_outputs(self):
        model = PredeterminedModel(outputs=["response1", "response2"])
        result1 = model.query([])
        assert result1["message"] == "response1"
        result2 = model.query([])
        assert result2["message"] == "response2"

    def test_dict_outputs(self):
        model = PredeterminedModel(outputs=[
            {"message": "hello"},
            {"message": "world", "tool_calls": [{"function": {"name": "test"}}]},
        ])
        result1 = model.query([])
        assert result1["message"] == "hello"
        result2 = model.query([])
        assert result2["message"] == "world"
        assert "tool_calls" in result2

    def test_tracks_api_calls(self):
        model = PredeterminedModel(outputs=["a", "b", "c"])
        assert model.stats.api_calls == 0
        model.query([])
        assert model.stats.api_calls == 1
        model.query([])
        assert model.stats.api_calls == 2

    def test_invalid_output_type(self):
        model = PredeterminedModel(outputs=[123])
        with pytest.raises(ValueError):
            model.query([])


class TestReplayModel:
    @pytest.fixture
    def replay_file(self, tmp_path):
        replay_data = [
            {"trajectory": ["action1", "action2", "submit"]},
        ]
        file_path = tmp_path / "replay.jsonl"
        with open(file_path, "w") as f:
            for item in replay_data:
                f.write(json.dumps(item) + "\n")
        return file_path

    def test_replays_actions(self, replay_file):
        config = ReplayModelConfig(replay_path=replay_file)
        model = ReplayModel(config)

        result1 = model.query([])
        assert result1["message"] == "action1"

        result2 = model.query([])
        assert result2["message"] == "action2"

    def test_submits_when_out_of_actions(self, tmp_path):
        replay_data = [{"trajectory": ["only_action"]}]
        file_path = tmp_path / "short.jsonl"
        with open(file_path, "w") as f:
            f.write(json.dumps(replay_data[0]) + "\n")

        config = ReplayModelConfig(replay_path=file_path)
        model = ReplayModel(config)

        model.query([])  # only_action
        result = model.query([])  # should auto-submit
        assert "submit" in result["message"]

    def test_file_not_found(self, tmp_path):
        config = ReplayModelConfig(replay_path=tmp_path / "nonexistent.jsonl")
        with pytest.raises(FileNotFoundError):
            ReplayModel(config)

    def test_tracks_api_calls(self, replay_file):
        config = ReplayModelConfig(replay_path=replay_file)
        model = ReplayModel(config)

        assert model.stats.api_calls == 0
        model.query([])
        assert model.stats.api_calls == 1

    def test_dict_actions(self, tmp_path):
        replay_data = [{
            "trajectory": [
                {"message": "hello", "tool_calls": [{"function": {"name": "test"}}]}
            ]
        }]
        file_path = tmp_path / "dict_replay.jsonl"
        with open(file_path, "w") as f:
            f.write(json.dumps(replay_data[0]) + "\n")

        config = ReplayModelConfig(replay_path=file_path)
        model = ReplayModel(config)

        result = model.query([])
        assert result["message"] == "hello"
        assert "tool_calls" in result


class TestCostTrackingModel:
    def test_instance_cost_limit(self):
        config = ModelConfig(name="test", per_instance_cost_limit=0.1)
        model = CostTrackingModel(config)

        model._update_stats(input_tokens=100, output_tokens=50, cost=0.05)
        assert model.stats.instance_cost == 0.05

        with pytest.raises(InstanceCostLimitExceededError):
            model._update_stats(input_tokens=100, output_tokens=50, cost=0.1)

    def test_total_cost_limit(self):
        GLOBAL_STATS.total_cost = 0
        config = ModelConfig(name="test", total_cost_limit=0.1)
        model = CostTrackingModel(config)

        model._update_stats(input_tokens=100, output_tokens=50, cost=0.05)

        with pytest.raises(TotalCostLimitExceededError):
            model._update_stats(input_tokens=100, output_tokens=50, cost=0.1)

    def test_call_limit(self):
        config = ModelConfig(name="test", per_instance_call_limit=2)
        model = CostTrackingModel(config)

        model._update_stats(input_tokens=10, output_tokens=10, cost=0.01)
        model._update_stats(input_tokens=10, output_tokens=10, cost=0.01)

        with pytest.raises(InstanceCallLimitExceededError):
            model._update_stats(input_tokens=10, output_tokens=10, cost=0.01)

    def test_tracks_tokens(self):
        config = ModelConfig(name="test")
        model = CostTrackingModel(config)

        model._update_stats(input_tokens=100, output_tokens=50, cost=0.01)
        assert model.stats.tokens_sent == 100
        assert model.stats.tokens_received == 50

        model._update_stats(input_tokens=200, output_tokens=100, cost=0.02)
        assert model.stats.tokens_sent == 300
        assert model.stats.tokens_received == 150

    def test_zero_limits_disabled(self):
        config = ModelConfig(
            name="test",
            per_instance_cost_limit=0,
            total_cost_limit=0,
            per_instance_call_limit=0,
        )
        model = CostTrackingModel(config)

        for _ in range(10):
            model._update_stats(input_tokens=1000, output_tokens=1000, cost=10.0)

        assert model.stats.api_calls == 10
        assert model.stats.instance_cost == 100.0


class TestReplayModelConfig:
    def test_defaults(self, tmp_path):
        file_path = tmp_path / "test.jsonl"
        file_path.write_text("{}")

        config = ReplayModelConfig(replay_path=file_path)
        assert config.name == "replay"
        assert config.per_instance_cost_limit == 0.0
        assert config.total_cost_limit == 0.0
