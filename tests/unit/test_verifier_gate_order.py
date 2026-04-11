"""Regression test — verify pipeline gate registration order.

Ensures spec_verify runs before review so spec-coverage gaps surface before
the expensive review retry loop begins. See change: reduce-change-retry-waste.

This test reads the verifier.py source and extracts the sequence of
pipeline.register("<name>", ...) calls inside handle_change_done. It does not
mock or execute the pipeline — it simply asserts the static registration
order matches the expected sequence.
"""

import ast
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

VERIFIER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "lib", "set_orch", "verifier.py"
)

EXPECTED_ORDER = [
    "build",
    "test",
    "e2e",
    "lint",
    "scope_check",
    "test_files",
    "e2e_coverage",
    "spec_verify",
    "rules",
    "review",
]


def _collect_register_calls(func_node: ast.FunctionDef) -> list[str]:
    """Walk a function AST and return gate names of pipeline.register(...) calls in source (line) order."""
    entries: list[tuple[int, str]] = []
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "register"):
            continue
        if not (isinstance(fn.value, ast.Name) and fn.value.id == "pipeline"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            entries.append((node.lineno, first.value))
    entries.sort(key=lambda t: t[0])
    return [name for _, name in entries]


def test_verify_pipeline_gate_registration_order():
    with open(VERIFIER_PATH) as f:
        tree = ast.parse(f.read())
    verify_fn = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == "handle_change_done"),
        None,
    )
    assert verify_fn is not None, "handle_change_done function not found in verifier.py"

    registered = _collect_register_calls(verify_fn)
    assert registered == EXPECTED_ORDER, (
        f"Gate registration order mismatch.\n"
        f"Expected: {EXPECTED_ORDER}\n"
        f"Actual:   {registered}\n\n"
        f"spec_verify MUST run before review — see change reduce-change-retry-waste."
    )


def test_spec_verify_registered_before_review():
    """Explicit check: spec_verify index < review index."""
    with open(VERIFIER_PATH) as f:
        tree = ast.parse(f.read())
    verify_fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "handle_change_done"
    )
    registered = _collect_register_calls(verify_fn)
    sv = registered.index("spec_verify")
    rv = registered.index("review")
    assert sv < rv, f"spec_verify ({sv}) must come before review ({rv}) in {registered}"
