from __future__ import annotations

import re


def parse_log(log: str) -> dict[str, str]:
    """Parse test runner output into per-test results.

    Args:
        log: Full stdout+stderr output of `bash run_test.sh 2>&1`.

    Returns:
        Dict mapping test_id to status.
        - test_id: pytest native format (e.g. "tests/foo.py::TestClass::test_func")
        - status: one of "PASSED", "FAILED", "SKIPPED", "ERROR"
    """
    # Strip ANSI color codes
    log = re.sub(r"\x1b\[[0-9;]*m", "", log)

    results: dict[str, str] = {}

    # Match lines like:
    #   tests/foo.py::test_bar PASSED                               [ 50%]
    #   tests/foo.py::TestClass::test_bar FAILED                    [ 75%]
    #   tests/foo.py::test_baz XFAIL                                [  9%]
    inline_pattern = re.compile(
        r"^(tests/\S.*?)\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\s+\[\s*\d+%\]",
        re.MULTILINE,
    )
    for m in inline_pattern.finditer(log):
        test_id = m.group(1).strip()
        raw_status = m.group(2)
        status = _normalize_status(raw_status)
        results.setdefault(test_id, status)

    # Also handle short-form summary lines:
    #   PASSED tests/foo.py::test_bar
    #   FAILED tests/foo.py::test_bar - <reason>
    summary_pattern = re.compile(
        r"^(PASSED|FAILED|SKIPPED|ERROR)\s+(tests/\S+?)(?:\s+-.*)?$",
        re.MULTILINE,
    )
    for m in summary_pattern.finditer(log):
        raw_status = m.group(1)
        test_id = m.group(2).strip()
        status = _normalize_status(raw_status)
        results.setdefault(test_id, status)

    # Handle collection errors: "ERROR tests/foo.py" (no "::")
    error_pattern = re.compile(r"^ERROR\s+(tests/[^\s:]+\.py)\s*$", re.MULTILINE)
    for m in error_pattern.finditer(log):
        test_id = m.group(1).strip()
        results.setdefault(test_id, "ERROR")

    return results


def _normalize_status(raw: str) -> str:
    mapping = {
        "PASSED": "PASSED",
        "FAILED": "FAILED",
        "SKIPPED": "SKIPPED",
        "ERROR": "ERROR",
        "XFAIL": "SKIPPED",  # expected failure → treat as skipped
        "XPASS": "PASSED",   # unexpected pass → treat as passed
    }
    return mapping.get(raw, "ERROR")

