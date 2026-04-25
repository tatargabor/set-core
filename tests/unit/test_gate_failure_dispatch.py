"""AST-level invariant: gate-failure paths must dispatch or terminate explicitly.

Background: in craftbrew-run-20260423-2223, `subscription-management` was stuck
in `integration-failed` because the merger's integration-test fail path
returned False without dispatching the agent or emitting a terminal event.
Commit `db2e6a5c` fixed it. This test prevents regressions: any new function
in `merger.py` or `verifier.py` that returns a fail-status without one of:
  (a) calling `resume_change(state_file, change_name)` with retry_context
  (b) emitting a `CHANGE_FAILED` / `CHANGE_INTEGRATION_FAILED` event
  (c) carrying a `# fail-dispatch-exempt: <reason>` comment on the same block
... will fail this test.

The check is heuristic, not perfect — it focuses on functions whose name or
docstring suggests they handle gate failures. False positives are tolerable;
operators can add the exempt comment.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_FILES = [
    REPO_ROOT / "lib" / "set_orch" / "merger.py",
    REPO_ROOT / "lib" / "set_orch" / "verifier.py",
]

# Functions whose names match these patterns are gate-failure handlers.
GATE_FAILURE_NAME_PATTERNS = (
    re.compile(r"_handle_.*_failure", re.IGNORECASE),
    re.compile(r"_handle_.*_fail", re.IGNORECASE),
    re.compile(r"_run_integration_gates", re.IGNORECASE),
    re.compile(r"_handle_blocking_failure", re.IGNORECASE),
)

# Calls that count as "dispatched" — the agent will be re-engaged.
DISPATCH_CALL_NAMES = {
    "resume_change",
    "redispatch_change",
    "escalate_change_to_fix_iss",
}

# Event-bus emit calls that count as "terminal failure" — the change is dead
# and the operator/sentinel will see it.
TERMINAL_EVENT_NAMES = {
    "CHANGE_FAILED",
    "CHANGE_INTEGRATION_FAILED",
    "TOKEN_RUNAWAY",
    "RETRY_WALL_TIME_EXHAUSTED",
}

EXEMPT_COMMENT_RE = re.compile(r"#\s*fail-dispatch-exempt", re.IGNORECASE)


def _function_has_dispatch_call(func: ast.FunctionDef) -> bool:
    """Walk function body for dispatch call patterns."""
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            target = None
            if isinstance(node.func, ast.Name):
                target = node.func.id
            elif isinstance(node.func, ast.Attribute):
                target = node.func.attr
            if target in DISPATCH_CALL_NAMES:
                return True
            # event_bus.emit("CHANGE_FAILED", ...) pattern
            if (
                target == "emit"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in TERMINAL_EVENT_NAMES
            ):
                return True
    return False


def _function_has_exempt_comment(func: ast.FunctionDef, source_lines: list[str]) -> bool:
    """Check if the function body or its decorator contains the exempt comment."""
    start = func.lineno - 1
    end = func.end_lineno or (start + 1)
    for line in source_lines[start:end]:
        if EXEMPT_COMMENT_RE.search(line):
            return True
    return False


def _is_gate_failure_function(func: ast.FunctionDef) -> bool:
    """Heuristic: function name matches a gate-failure pattern."""
    return any(p.match(func.name) for p in GATE_FAILURE_NAME_PATTERNS)


@pytest.mark.parametrize("source_path", TARGET_FILES, ids=lambda p: p.name)
def test_gate_failure_paths_dispatch_or_terminate(source_path: Path):
    assert source_path.exists(), f"Target file missing: {source_path}"
    source = source_path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    tree = ast.parse(source, filename=str(source_path))

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _is_gate_failure_function(node):
                continue
            if _function_has_exempt_comment(node, source_lines):
                continue
            if _function_has_dispatch_call(node):
                continue
            violations.append(
                f"{source_path.name}:{node.lineno}: "
                f"function `{node.name}` matches gate-failure naming pattern but "
                f"does not call any of {sorted(DISPATCH_CALL_NAMES)} OR emit "
                f"any of {sorted(TERMINAL_EVENT_NAMES)}. "
                f"Either add a dispatch call or mark with `# fail-dispatch-exempt: <reason>`."
            )

    assert not violations, (
        "Silent gate-failure return paths detected — these would silently "
        "stall the orchestration without re-engaging the agent. Violations:\n"
        + "\n".join(violations)
    )
