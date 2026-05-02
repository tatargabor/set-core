"""Static-analysis regression: every VERIFY_GATE emit MUST include gate+result keys.

See spec verify-gate-event-schema (observability-event-file-unification).
"""

import ast
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETS = [
    REPO_ROOT / "lib" / "set_orch" / "verifier.py",
    REPO_ROOT / "lib" / "set_orch" / "merger.py",
]


def _collect_verify_gate_emits(file_path: Path) -> list:
    """Return list of (lineno, dict_keys_or_None) for every event_bus.emit("VERIFY_GATE", ...) call.

    `dict_keys_or_None` is:
      - the set of literal string keys when the data argument is a Dict node,
      - None when the data argument is a Name (variable) — the test then
        scans the enclosing function for any assignment to that name and
        merges the keys it finds in the literal dict construction.
    """
    src = file_path.read_text()
    tree = ast.parse(src)
    emits: list = []

    # Index function-body assignments to dict literals so we can resolve
    # `_retry_evt`-style references back to their construction site.
    name_to_keys: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and isinstance(node.value, ast.Dict):
                    keys = set()
                    for k in node.value.keys:
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            keys.add(k.value)
                    name_to_keys[tgt.id] = keys
        if isinstance(node, ast.AnnAssign):
            if (isinstance(node.target, ast.Name)
                    and isinstance(node.value, ast.Dict)):
                keys = set()
                for k in node.value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
                name_to_keys[node.target.id] = keys

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match event_bus.emit("VERIFY_GATE", ...) AND
        #       self.event_bus.emit(...) shape too.
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "emit"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and first.value == "VERIFY_GATE"):
            continue

        # Find the `data=` keyword arg
        data_arg = None
        for kw in node.keywords:
            if kw.arg == "data":
                data_arg = kw.value
                break
        if data_arg is None:
            emits.append((node.lineno, None))
            continue

        if isinstance(data_arg, ast.Dict):
            keys = set()
            for k in data_arg.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
            emits.append((node.lineno, keys))
        elif isinstance(data_arg, ast.Name):
            emits.append((node.lineno, name_to_keys.get(data_arg.id)))
        else:
            emits.append((node.lineno, None))
    return emits


@pytest.mark.parametrize("target", TARGETS, ids=lambda p: p.name)
def test_every_verify_gate_emit_has_gate_and_result_keys(target: Path) -> None:
    """Every event_bus.emit('VERIFY_GATE', data=...) site MUST include
    'gate' and 'result' keys at the data dict's top level."""
    emits = _collect_verify_gate_emits(target)
    assert emits, f"No VERIFY_GATE emits found in {target.name} — test selector broken?"

    failures: list = []
    for lineno, keys in emits:
        if keys is None:
            failures.append(f"{target.name}:{lineno} — could not statically resolve data dict keys")
            continue
        missing = {"gate", "result"} - keys
        if missing:
            failures.append(f"{target.name}:{lineno} — missing keys: {sorted(missing)} (has: {sorted(keys)})")

    assert not failures, (
        "VERIFY_GATE schema violations:\n  " + "\n  ".join(failures)
    )


def test_total_verify_gate_emit_count_at_least_12() -> None:
    """Sanity: spec says all 12 emit sites should still exist (4 in verifier
    + 8 in merger). Prevents accidental removal without spec review."""
    total = sum(len(_collect_verify_gate_emits(t)) for t in TARGETS)
    assert total >= 12, (
        f"Expected at least 12 VERIFY_GATE emit sites across {[t.name for t in TARGETS]}, "
        f"found {total}. Did someone remove one without updating the spec?"
    )
