"""Tests for environment abstraction."""

import tempfile
from pathlib import Path

import pytest

from codeagent.environment import (
    EnvHook,
    CombinedEnvHooks,
    Repo,
    LocalRepoConfig,
    PreExistingRepoConfig,
    RepoConfig,
    repo_from_simplified_input,
    EnvironmentConfig,
    SWEEnv,
)
from codeagent.environment.repo import GithubRepoConfig


class TestRepoProtocol:
    def test_protocol_defines_required_attributes(self):
        """Protocol requires base_commit and repo_name."""
        assert "base_commit" in Repo.__annotations__
        assert "repo_name" in Repo.__annotations__

    def test_protocol_defines_required_methods(self):
        """Protocol requires copy and get_reset_commands methods."""
        assert callable(getattr(Repo, "copy", None))
        assert callable(getattr(Repo, "get_reset_commands", None))


class TestPreExistingRepoConfig:
    def test_creates_with_defaults(self):
        config = PreExistingRepoConfig(repo_name="my-repo")
        assert config.repo_name == "my-repo"
        assert config.base_commit == "HEAD"
        assert config.type == "preexisting"
        assert config.reset is True

    def test_copy_does_nothing(self):
        config = PreExistingRepoConfig(repo_name="repo")
        config.copy(None)

    def test_get_reset_commands_with_reset_true(self):
        config = PreExistingRepoConfig(repo_name="repo", reset=True)
        commands = config.get_reset_commands()
        assert len(commands) > 0
        assert any("git checkout" in cmd for cmd in commands)

    def test_get_reset_commands_with_reset_false(self):
        config = PreExistingRepoConfig(repo_name="repo", reset=False)
        commands = config.get_reset_commands()
        assert commands == []


class TestLocalRepoConfig:
    def test_creates_with_path(self):
        config = LocalRepoConfig(path=Path("/some/path"))
        assert config.path == Path("/some/path")
        assert config.base_commit == "HEAD"
        assert config.type == "local"

    def test_repo_name_from_path(self):
        config = LocalRepoConfig(path=Path("/home/user/my-project"))
        assert config.repo_name == "my-project"

    def test_repo_name_sanitizes_spaces(self):
        config = LocalRepoConfig(path=Path("/home/user/my project"))
        assert " " not in config.repo_name

    def test_check_valid_repo_raises_for_non_git(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = LocalRepoConfig(path=Path(tmpdir))
            with pytest.raises(ValueError, match="Could not find git repository"):
                config.check_valid_repo()

    def test_check_valid_repo_passes_for_git_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            config = LocalRepoConfig(path=Path(tmpdir))
            result = config.check_valid_repo()
            assert result == config

    def test_get_reset_commands(self):
        config = LocalRepoConfig(path=Path("/some/path"))
        commands = config.get_reset_commands()
        assert len(commands) > 0
        assert any("git checkout" in cmd for cmd in commands)


class TestGithubRepoConfig:
    def test_creates_with_full_url(self):
        config = GithubRepoConfig(github_url="https://github.com/owner/repo")
        assert config.github_url == "https://github.com/owner/repo"
        assert config.type == "github"

    def test_expands_shorthand_url(self):
        config = GithubRepoConfig(github_url="owner/repo")
        assert config.github_url == "https://github.com/owner/repo"

    def test_repo_name_from_url(self):
        config = GithubRepoConfig(github_url="https://github.com/owner/repo")
        assert config.repo_name == "owner__repo"

    def test_repo_name_strips_git_suffix(self):
        config = GithubRepoConfig(github_url="https://github.com/owner/repo.git")
        assert config.repo_name == "owner__repo"

    def test_get_reset_commands(self):
        config = GithubRepoConfig(github_url="owner/repo")
        commands = config.get_reset_commands()
        assert len(commands) > 0


class TestRepoFromSimplifiedInput:
    def test_auto_detects_github_url(self):
        config = repo_from_simplified_input(input="https://github.com/owner/repo")
        assert isinstance(config, GithubRepoConfig)

    def test_auto_detects_local_path(self):
        config = repo_from_simplified_input(input="/some/local/path")
        assert isinstance(config, LocalRepoConfig)

    def test_explicit_local_type(self):
        config = repo_from_simplified_input(input="/path", type="local")
        assert isinstance(config, LocalRepoConfig)

    def test_explicit_github_type(self):
        config = repo_from_simplified_input(input="owner/repo", type="github")
        assert isinstance(config, GithubRepoConfig)

    def test_explicit_preexisting_type(self):
        config = repo_from_simplified_input(input="my-repo", type="preexisting")
        assert isinstance(config, PreExistingRepoConfig)

    def test_custom_base_commit(self):
        config = repo_from_simplified_input(
            input="/path", type="local", base_commit="abc123"
        )
        assert config.base_commit == "abc123"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown repo type"):
            repo_from_simplified_input(input="/path", type="unknown")  # type: ignore


class TestEnvHook:
    def test_default_methods_do_nothing(self):
        hook = EnvHook()
        hook.on_init(env=None)
        hook.on_copy_repo_started(repo=None)
        hook.on_start_deployment()
        hook.on_install_env_started()
        hook.on_close()
        hook.on_environment_startup()


class TestCombinedEnvHooks:
    def test_aggregates_hooks(self):
        combined = CombinedEnvHooks()
        calls = []

        class TrackingHook(EnvHook):
            def __init__(self, name: str):
                self.name = name

            def on_close(self):
                calls.append(self.name)

        combined.add_hook(TrackingHook("first"))
        combined.add_hook(TrackingHook("second"))
        combined.on_close()

        assert calls == ["first", "second"]

    def test_all_lifecycle_methods(self):
        combined = CombinedEnvHooks()
        events = []

        class AllEventsHook(EnvHook):
            def on_init(self, *, env):
                events.append("init")

            def on_copy_repo_started(self, repo):
                events.append("copy")

            def on_start_deployment(self):
                events.append("start")

            def on_install_env_started(self):
                events.append("install")

            def on_close(self):
                events.append("close")

            def on_environment_startup(self):
                events.append("startup")

        combined.add_hook(AllEventsHook())

        combined.on_init(env=None)
        combined.on_copy_repo_started(repo=None)
        combined.on_start_deployment()
        combined.on_install_env_started()
        combined.on_close()
        combined.on_environment_startup()

        assert events == ["init", "copy", "start", "install", "close", "startup"]


class TestEnvironmentConfig:
    def test_default_values(self):
        config = EnvironmentConfig()
        assert config.repo is None
        assert config.post_startup_commands == []
        assert config.post_startup_command_timeout == 500
        assert config.name == "main"

    def test_custom_values(self):
        repo = PreExistingRepoConfig(repo_name="test")
        config = EnvironmentConfig(
            repo=repo,
            post_startup_commands=["echo hello"],
            name="custom",
        )
        assert config.repo == repo
        assert config.post_startup_commands == ["echo hello"]
        assert config.name == "custom"


class TestSWEEnv:
    def test_creates_without_repo(self):
        env = SWEEnv()
        assert env.repo is None
        assert env.name == "main"

    def test_creates_with_repo(self):
        repo = PreExistingRepoConfig(repo_name="test")
        env = SWEEnv(repo=repo)
        assert env.repo == repo

    def test_from_config(self):
        config = EnvironmentConfig(name="test-env")
        env = SWEEnv.from_config(config)
        assert env.name == "test-env"

    def test_add_hook(self):
        env = SWEEnv()
        events = []

        class TestHook(EnvHook):
            def on_init(self, *, env):
                events.append("init")

        env.add_hook(TestHook())
        assert "init" in events

    def test_working_directory_without_repo(self):
        env = SWEEnv()
        assert env.working_directory is None

    def test_working_directory_with_repo(self):
        repo = PreExistingRepoConfig(repo_name="my-repo")
        env = SWEEnv(repo=repo)
        assert env.working_directory == Path("/my-repo")

    def test_working_directory_override(self):
        env = SWEEnv(working_directory=Path("/custom"))
        assert env.working_directory == Path("/custom")

    def test_start_and_close(self):
        events = []

        class TrackingHook(EnvHook):
            def on_start_deployment(self):
                events.append("start")

            def on_environment_startup(self):
                events.append("startup")

            def on_close(self):
                events.append("close")

        env = SWEEnv(hooks=[TrackingHook()])
        env.start()
        assert env.is_started is True
        assert "start" in events
        assert "startup" in events

        env.close()
        assert env.is_started is False
        assert "close" in events

    def test_communicate_simple_command(self):
        env = SWEEnv()
        output = env.communicate("echo hello")
        assert "hello" in output

    def test_communicate_with_timeout(self):
        env = SWEEnv()
        output = env.communicate("echo quick", timeout=10)
        assert "quick" in output

    def test_communicate_check_raise(self):
        env = SWEEnv()
        with pytest.raises(RuntimeError):
            env.communicate("exit 1", check="raise")

    def test_communicate_check_ignore(self):
        env = SWEEnv()
        output = env.communicate("exit 1", check="ignore")
        assert output is not None

    def test_read_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            f.flush()
            path = Path(f.name)

        try:
            env = SWEEnv()
            content = env.read_file(path)
            assert content == "test content"
        finally:
            path.unlink()

    def test_write_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            env = SWEEnv()
            env.write_file(path, "written content")
            assert path.read_text() == "written content"

    def test_set_env_variables(self):
        env = SWEEnv()
        env.set_env_variables({"MY_VAR": "my_value"})
        assert env._env_variables["MY_VAR"] == "my_value"

    def test_execute_command(self):
        env = SWEEnv()
        result = env.execute_command("echo test")
        assert result.returncode == 0
        assert "test" in result.stdout

    def test_hard_reset(self):
        events = []

        class TrackingHook(EnvHook):
            def on_close(self):
                events.append("close")

            def on_start_deployment(self):
                events.append("start")

        env = SWEEnv(hooks=[TrackingHook()])
        env.start()
        events.clear()

        env.hard_reset()
        assert "close" in events
        assert "start" in events


class TestSWEEnvWithPostStartupCommands:
    def test_executes_post_startup_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            marker_file = Path(tmpdir) / "marker.txt"
            env = SWEEnv(
                post_startup_commands=[f"touch {marker_file}"],
                post_startup_command_timeout=10,
            )
            env.start()
            assert marker_file.exists()
