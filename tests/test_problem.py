"""Tests for problem statement types."""

import tempfile
from pathlib import Path

import pytest

from codeagent.problem import (
    ProblemStatement,
    BaseProblemStatement,
    EmptyProblemStatement,
    TextProblemStatement,
    FileProblemStatement,
)


class TestProblemStatementProtocol:
    def test_protocol_defines_required_attributes(self):
        """Protocol requires id attribute."""
        assert "id" in ProblemStatement.__annotations__

    def test_protocol_defines_required_methods(self):
        """Protocol requires get_problem_statement and get_extra_fields methods."""
        assert callable(getattr(ProblemStatement, "get_problem_statement", None))
        assert callable(getattr(ProblemStatement, "get_extra_fields", None))


class TestEmptyProblemStatement:
    def test_returns_empty_string(self):
        stmt = EmptyProblemStatement()
        assert stmt.get_problem_statement() == ""

    def test_generates_uuid_id(self):
        stmt = EmptyProblemStatement()
        assert stmt.id is not None
        assert len(stmt.id) == 36  # UUID format

    def test_different_instances_have_different_ids(self):
        stmt1 = EmptyProblemStatement()
        stmt2 = EmptyProblemStatement()
        assert stmt1.id != stmt2.id

    def test_type_is_empty(self):
        stmt = EmptyProblemStatement()
        assert stmt.type == "empty"

    def test_extra_fields_returns_empty_dict(self):
        stmt = EmptyProblemStatement()
        assert stmt.get_extra_fields() == {}

    def test_get_problem_statement_for_env(self):
        stmt = EmptyProblemStatement()
        assert stmt.get_problem_statement_for_env() == ""


class TestTextProblemStatement:
    def test_returns_provided_text(self):
        stmt = TextProblemStatement(text="Fix the bug in auth.py")
        assert stmt.get_problem_statement() == "Fix the bug in auth.py"

    def test_auto_generates_id_from_hash(self):
        stmt = TextProblemStatement(text="Some problem text")
        assert stmt.id is not None
        assert len(stmt.id) == 6  # First 6 chars of sha256

    def test_same_text_produces_same_id(self):
        stmt1 = TextProblemStatement(text="Same text")
        stmt2 = TextProblemStatement(text="Same text")
        assert stmt1.id == stmt2.id

    def test_different_text_produces_different_id(self):
        stmt1 = TextProblemStatement(text="Text one")
        stmt2 = TextProblemStatement(text="Text two")
        assert stmt1.id != stmt2.id

    def test_custom_id_overrides_auto_generated(self):
        stmt = TextProblemStatement(text="Some text", id="custom-id")
        assert stmt.id == "custom-id"

    def test_type_is_text(self):
        stmt = TextProblemStatement(text="Hello")
        assert stmt.type == "text"

    def test_extra_fields_returns_configured_fields(self):
        extra = {"repo": "test/repo", "issue_id": 123}
        stmt = TextProblemStatement(text="Problem", extra_fields=extra)
        assert stmt.get_extra_fields() == extra

    def test_extra_fields_default_empty(self):
        stmt = TextProblemStatement(text="Problem")
        assert stmt.get_extra_fields() == {}

    def test_repr_short_text(self):
        stmt = TextProblemStatement(text="Short")
        repr_str = repr(stmt)
        assert "TextProblemStatement" in repr_str
        assert "Short" in repr_str

    def test_repr_long_text_truncated(self):
        long_text = "A" * 100
        stmt = TextProblemStatement(text=long_text)
        repr_str = repr(stmt)
        assert "..." in repr_str
        assert len(repr_str) < 100

    def test_get_problem_statement_for_env(self):
        stmt = TextProblemStatement(text="Problem text")
        assert stmt.get_problem_statement_for_env() == "Problem text"


class TestFileProblemStatement:
    def test_reads_content_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Problem from file")
            f.flush()
            path = Path(f.name)

        try:
            stmt = FileProblemStatement(path=path)
            assert stmt.get_problem_statement() == "Problem from file"
        finally:
            path.unlink()

    def test_auto_generates_id_from_content_hash(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("File content")
            f.flush()
            path = Path(f.name)

        try:
            stmt = FileProblemStatement(path=path)
            assert stmt.id is not None
            assert len(stmt.id) == 6
        finally:
            path.unlink()

    def test_same_content_produces_same_id(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f1:
            f1.write("Same content")
            f1.flush()
            path1 = Path(f1.name)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f2:
            f2.write("Same content")
            f2.flush()
            path2 = Path(f2.name)

        try:
            stmt1 = FileProblemStatement(path=path1)
            stmt2 = FileProblemStatement(path=path2)
            assert stmt1.id == stmt2.id
        finally:
            path1.unlink()
            path2.unlink()

    def test_custom_id_overrides_auto_generated(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Content")
            f.flush()
            path = Path(f.name)

        try:
            stmt = FileProblemStatement(path=path, id="my-custom-id")
            assert stmt.id == "my-custom-id"
        finally:
            path.unlink()

    def test_type_is_text_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Content")
            f.flush()
            path = Path(f.name)

        try:
            stmt = FileProblemStatement(path=path)
            assert stmt.type == "text_file"
        finally:
            path.unlink()

    def test_extra_fields_returns_configured_fields(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Content")
            f.flush()
            path = Path(f.name)

        try:
            extra = {"source": "github", "pr_number": 456}
            stmt = FileProblemStatement(path=path, extra_fields=extra)
            assert stmt.get_extra_fields() == extra
        finally:
            path.unlink()

    def test_extra_fields_default_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Content")
            f.flush()
            path = Path(f.name)

        try:
            stmt = FileProblemStatement(path=path)
            assert stmt.get_extra_fields() == {}
        finally:
            path.unlink()

    def test_file_not_found_raises_error(self):
        stmt = FileProblemStatement(path=Path("/nonexistent/file.txt"), id="test")
        with pytest.raises(FileNotFoundError):
            stmt.get_problem_statement()

    def test_get_problem_statement_for_env(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Env problem")
            f.flush()
            path = Path(f.name)

        try:
            stmt = FileProblemStatement(path=path)
            assert stmt.get_problem_statement_for_env() == "Env problem"
        finally:
            path.unlink()


class TestBaseProblemStatement:
    def test_get_problem_statement_not_implemented(self):
        stmt = BaseProblemStatement()
        with pytest.raises(NotImplementedError):
            stmt.get_problem_statement()

    def test_get_extra_fields_returns_empty(self):
        stmt = BaseProblemStatement()
        assert stmt.get_extra_fields() == {}

    def test_get_problem_statement_for_env_calls_get_problem_statement(self):
        class CustomStatement(BaseProblemStatement):
            def get_problem_statement(self) -> str:
                return "Custom problem"

        stmt = CustomStatement()
        assert stmt.get_problem_statement_for_env() == "Custom problem"
