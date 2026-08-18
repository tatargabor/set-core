"""The dependency between the work-cycle engine and orchestration points ONE way.

    set_workcycle  ->  set_orch        allowed, and exercised below
    set_orch       ->  set_workcycle   forbidden, and this file fails if it appears

Written with the change `work-cycle-engine-apply-first`, whose design (D10) states the
direction as a **requirement rather than a preference**: it is what makes "orchestration keeps
working with the engine deleted" a fact that can be checked instead of a sentence in a comment.

Three checks, because a static scan alone would be a proxy:

1. **Direct imports** — every ``set_orch`` source file is parsed and its import statements
   inspected. An AST walk rather than a substring search, so a comment or a docstring that
   merely *names* the package does not fail the suite. (A bare ``"set_workcycle" in text``
   check would be the substring defect this repo has already paid for elsewhere.)
2. **Dynamic imports** — ``importlib.import_module("set_workcycle")`` and
   ``__import__("set_workcycle")`` carry the name in a string, where the AST walk in (1) sees
   no import at all. Matched textually, on purpose, and only in that call shape.
3. **The thing itself, not its trace** — importing ``set_orch`` in a subprocess must not pull
   ``set_workcycle`` into ``sys.modules``. This is the check that survives a *transitive*
   route, which neither (1) nor (2) can see: ``set_orch`` importing a third module that
   imports the engine.

**Scope, stated so a later reader does not widen it silently:** the forbidden direction is
about ``lib/set_orch``. ``modules/`` and ``tests/`` are not scanned — this file itself names
the package repeatedly, and a scan whose corpus contains the scanner is the measurement-inside-
the-corpus defect. It lives under ``tests/`` precisely so it cannot match itself.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "lib"
sys.path.insert(0, str(LIB))

#: The package whose name must not appear as an import inside orchestration.
ENGINE_PKG = "set_workcycle"
#: The package that must not depend on it.
ORCH_DIR = LIB / "set_orch"

#: `importlib.import_module("set_workcycle…")` / `__import__("set_workcycle…")`, single or
#: double quoted. Deliberately narrow: it matches the call shape, not the bare name.
_DYNAMIC_IMPORT = re.compile(
    r"""(?:importlib\.import_module|__import__)\s*\(\s*['"]%s(?:[.'"]|$)""" % ENGINE_PKG
)


def _orch_sources() -> list[Path]:
    return sorted(p for p in ORCH_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _direct_engine_imports(path: Path) -> list[tuple[int, str]]:
    """Import statements in `path` that name the engine package. AST, not substring."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:  # a file that will not parse cannot be cleared silently
        pytest.fail(f"{path.relative_to(REPO)} does not parse: {exc}")
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == ENGINE_PKG or alias.name.startswith(ENGINE_PKG + "."):
                    hits.append((node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == ENGINE_PKG or mod.startswith(ENGINE_PKG + "."):
                hits.append((node.lineno, f"from {mod} import ..."))
    return hits


def test_the_engine_package_exists_and_imports():
    """Guard the guard: with no package, every check below would pass vacuously."""
    import set_workcycle

    assert Path(set_workcycle.__file__).resolve().is_relative_to(LIB.resolve())
    assert set_workcycle.__version__


def test_the_engine_may_import_orchestration():
    """The permitted direction, exercised rather than assumed."""
    proc = subprocess.run(
        [sys.executable, "-c",
         "import set_workcycle, set_orch.paths; print(set_orch.paths.__name__)"],
        cwd=str(REPO), env={"PYTHONPATH": str(LIB), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "set_orch.paths" in proc.stdout


def test_orchestration_does_not_import_the_engine_directly():
    """(1) Direct `import` / `from … import` statements, across all of `lib/set_orch`."""
    sources = _orch_sources()
    assert sources, "no orchestration sources scanned — the scan itself is broken"

    offenders = [
        f"{path.relative_to(REPO)}:{line}: {what}"
        for path in sources
        for line, what in _direct_engine_imports(path)
    ]
    assert not offenders, (
        "set_orch must not import set_workcycle — the dependency points one way "
        "(see design.md D10):\n  " + "\n  ".join(offenders)
    )


def test_orchestration_does_not_import_the_engine_dynamically():
    """(2) The string-carried route an AST walk cannot see."""
    offenders = []
    for path in _orch_sources():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _DYNAMIC_IMPORT.search(line):
                offenders.append(f"{path.relative_to(REPO)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "set_orch must not import set_workcycle dynamically either:\n  " + "\n  ".join(offenders)
    )


def test_importing_orchestration_does_not_pull_in_the_engine():
    """(3) The thing, not its trace — catches a transitive route (1) and (2) are blind to."""
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys, set_orch\n"
         "leaked = sorted(m for m in sys.modules if m == 'set_workcycle' "
         "or m.startswith('set_workcycle.'))\n"
         "print('LEAKED:' + ','.join(leaked))"],
        cwd=str(REPO), env={"PYTHONPATH": str(LIB), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    line = [l for l in proc.stdout.splitlines() if l.startswith("LEAKED:")]
    assert line, f"probe produced no verdict: {proc.stdout!r} {proc.stderr!r}"
    leaked = [m for m in line[0][len("LEAKED:"):].split(",") if m]
    assert not leaked, (
        "importing set_orch pulled the engine into sys.modules "
        f"(transitive dependency): {leaked}"
    )
