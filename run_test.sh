#!/bin/bash
set -eo pipefail

export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export CI=true

cd /workspace/SWE-agent
rm -rf .pytest_cache

pytest -v --tb=short --no-cov -p no:cacheprovider -m "not slow" \
    --deselect tests/test_run_replay.py::test_replay \
    --deselect tests/test_env_utils.py::test_get_associated_commit_urls \
    --deselect tests/test_run_hooks.py::test_should_open_pr_fail_invalid_url \
    --deselect tests/test_run_hooks.py::test_should_open_pr_fail_closed \
    --deselect tests/test_run_hooks.py::test_should_open_pr_fail_has_pr \
    --deselect tests/test_run_hooks.py::test_should_open_pr_success_has_pr_override \
    --deselect tests/test_run_hooks.py::test_should_open_pr_fail_assigned \
    --deselect tests/test_run_hooks.py::test_should_open_pr_fail_locked \
    tests/

