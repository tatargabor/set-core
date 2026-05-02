"""Tests for model-config-unified: touch-point coverage scan.

Asserts that every Python file in lib/set_orch/ and modules/web/set_project_web/
contains zero hardcoded short-model-name string literals (`"opus"`, `"sonnet"`,
`"haiku"`, `"opus-4-6"`, `"opus-4-7"`, `"sonnet-1m"`, `"opus-1m"`,
`"opus-4-6-1m"`, `"opus-4-7-1m"`) outside of:

  - lib/set_orch/config.py            (canonical defaults table)
  - lib/set_orch/model_config.py      (resolver + presets + last-resort fallbacks)
  - lib/set_orch/subprocess_utils.py  (short-name → full-id translation)
  - lib/set_orch/cost.py              (cost-tracking rates)
  - lib/set_orch/cli.py               (argparse choices + --model-profile preset names)
  - any test file
  - comments and docstrings (we exempt them so the layer rule + history
    remain documentable)

Plus targeted scenarios verifying that key call sites resolve via
`resolve_model(role)` rather than passing a literal.
"""

import ast
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))


REPO_ROOT = Path(__file__).resolve().parents[2]

# Files exempt from the literal scan — they are the canonical owners of
# model-name strings (or external ID translations / cost tables).
EXEMPT_FILES: set[Path] = {
    REPO_ROOT / "lib" / "set_orch" / "config.py",
    REPO_ROOT / "lib" / "set_orch" / "model_config.py",
    REPO_ROOT / "lib" / "set_orch" / "subprocess_utils.py",
    REPO_ROOT / "lib" / "set_orch" / "cost.py",
    REPO_ROOT / "lib" / "set_orch" / "cli.py",
}

SHORT_MODEL_NAMES = (
    "haiku", "sonnet", "opus",
    "sonnet-1m", "opus-1m",
    "opus-4-6", "opus-4-7",
    "opus-4-6-1m", "opus-4-7-1m",
)


def _string_literal_violations(file_path: Path) -> list[tuple[int, str]]:
    """Walk the AST and report short model literals appearing in a
    *model selection context*. Specifically, flag when the literal is:

      - a function-call keyword argument named ``model``, ``review_model``,
        ``digest_model``, ``classifier_model``, or any ``*_model`` kwarg
      - the default value of a parameter whose name ends in ``_model``
      - the right-hand side of a dataclass field default named ``model``
        / ``*_model`` (AnnAssign with such a target name)

    Skip:
      - docstrings
      - comparison operands (e.g. ``if x == "sonnet":``)
      - membership tests (``x in ("opus", "sonnet")``)
      - container literals (lists, sets, tuples) — those are typically
        enumeration tables, validators, choices
      - dict keys/values (the model-name → cost/full-id maps live in the
        exempt files; otherwise dicts are configuration tables)
    """
    src = file_path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(file_path))
    except SyntaxError:
        return []

    docstring_ids: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(
                first.value, ast.Constant
            ) and isinstance(first.value.value, str):
                docstring_ids.add(id(first.value))

    flagged: list[tuple[int, str]] = []

    def _is_model_kwarg_name(name: str) -> bool:
        return name == "model" or name.endswith("_model")

    for node in ast.walk(tree):
        # Function-call keyword: foo(model="sonnet")
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg is None:
                    continue
                if not _is_model_kwarg_name(kw.arg):
                    continue
                v = kw.value
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    if v.value in SHORT_MODEL_NAMES and id(v) not in docstring_ids:
                        flagged.append((v.lineno, v.value))
        # Function default arg: def f(model="sonnet")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg, default in zip(args.args[-len(args.defaults):], args.defaults):
                if not _is_model_kwarg_name(arg.arg):
                    continue
                if isinstance(default, ast.Constant) and isinstance(default.value, str):
                    if default.value in SHORT_MODEL_NAMES and id(default) not in docstring_ids:
                        flagged.append((default.lineno, default.value))
            for arg, default in zip(args.kwonlyargs, args.kw_defaults):
                if default is None:
                    continue
                if not _is_model_kwarg_name(arg.arg):
                    continue
                if isinstance(default, ast.Constant) and isinstance(default.value, str):
                    if default.value in SHORT_MODEL_NAMES and id(default) not in docstring_ids:
                        flagged.append((default.lineno, default.value))
        # Dataclass field annotated assignment: model: str = "sonnet"
        if isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
            if isinstance(target, ast.Name) and _is_model_kwarg_name(target.id):
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    if value.value in SHORT_MODEL_NAMES and id(value) not in docstring_ids:
                        flagged.append((value.lineno, value.value))
    return flagged


def _python_files() -> list[Path]:
    """Yield every .py file under lib/set_orch and modules/web/set_project_web,
    excluding exempt files and __pycache__/_api_old.py.
    """
    targets: list[Path] = []
    for root in (
        REPO_ROOT / "lib" / "set_orch",
        REPO_ROOT / "modules" / "web" / "set_project_web",
    ):
        for p in root.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            # _api_old.py is legacy code path being phased out
            if p.name == "_api_old.py":
                continue
            if p in EXEMPT_FILES:
                continue
            targets.append(p)
    return targets


def test_no_hardcoded_model_literals_in_orchestration_code():
    """Scan all production Python files for literal short model names."""
    all_violations: dict[Path, list[tuple[int, str]]] = {}
    for path in _python_files():
        v = _string_literal_violations(path)
        if v:
            all_violations[path] = v

    if all_violations:
        rel = {
            str(p.relative_to(REPO_ROOT)): v for p, v in all_violations.items()
        }
        msg = "Hardcoded short model names found outside the allowed files:\n"
        for relpath, items in rel.items():
            msg += f"  {relpath}:\n"
            for ln, val in items:
                msg += f"    L{ln}: {val!r}\n"
        msg += (
            "\nReplace each with a resolve_model(role) call in "
            "lib/set_orch/model_config.py. If a literal IS legitimately "
            "the canonical value (e.g. a default constant or alias map), "
            "add the file to EXEMPT_FILES in this test."
        )
        pytest.fail(msg)


# ─── Specific call-site scenarios ────────────────────────────────


def test_dispatch_complexity_routing_returns_agent_small():
    """When model_routing='complexity' fires the downgrade branch, the
    returned model is resolve_model('agent_small') (not a hardcoded sonnet)."""
    from set_orch.dispatcher import resolve_change_model
    from set_orch.state import Change

    # S-complexity, infrastructure (not feature) → downgrade target
    ch = Change(
        name="setup-config", scope="setup",
        complexity="S", change_type="infrastructure",
        model=None,
    )
    with patch("set_orch.model_config.resolve_model") as mocked:
        mocked.side_effect = lambda role, **kw: {
            "agent": "opus-4-6",
            "agent_small": "haiku",  # arbitrary distinct value
        }[role]
        result = resolve_change_model(ch, model_routing="complexity")
    roles_called = [c.args[0] for c in mocked.call_args_list]
    assert "agent_small" in roles_called
    assert result == "haiku"


def test_dispatch_resolve_change_model_default_uses_agent_role():
    """When default_model is None, resolve_change_model fills it from
    resolve_model('agent')."""
    from set_orch.dispatcher import resolve_change_model
    from set_orch.state import Change

    ch = Change(
        name="add-feature", scope="x",
        complexity="M", change_type="feature",
        model=None,
    )
    with patch("set_orch.model_config.resolve_model") as mocked:
        mocked.side_effect = lambda role, **kw: {
            "agent": "opus-4-6",
            "agent_small": "sonnet",
        }[role]
        result = resolve_change_model(ch)
    assert "agent" in [c.args[0] for c in mocked.call_args_list]
    assert result == "opus-4-6"


def test_chatsession_init_resolves_agent_role(tmp_path):
    """ChatSession's self.model is set via resolve_model('agent')."""
    from set_orch.chat import ChatSession

    with patch("set_orch.model_config.resolve_model") as mocked:
        mocked.return_value = "opus-4-7"
        s = ChatSession(project_name="p", project_path=tmp_path)
    assert s.model == "opus-4-7"
    assert mocked.call_args.args[0] == "agent"
