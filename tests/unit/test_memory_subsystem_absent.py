"""The memory subsystem is gone, and stays gone.

These are absence tests, which is an unusual and slightly awkward shape: they pass
trivially today and their whole job is to fail the day somebody reintroduces the thing.
That is deliberate. The subsystem was removed on 2026-08-22 because it injected a false
claim about the user into unrelated sessions — 168 of 187 injections over 21 days were
`User frustrated` records produced by a detector that fired on exclamation marks — and the
cheapest way for it to come back is a file restored from a branch, a hook re-added by a
deploy, or an import quietly re-linked.

See `openspec/changes/remove-shodh-memory`.

Each test states what a FAILURE means, because an absence test that fails reads at first
glance like a broken test rather than a returned subsystem.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# The command prefixes the framework must never install again.
FORBIDDEN_BIN_PREFIXES = ("set-memory", "set-hook-memory")

# The packages that no first-party module may import.
FORBIDDEN_IMPORTS = ("shodh_memory", "set_memoryd", "set_hooks")


def test_no_memory_executable_is_installed():
    """A failure here means an executable came back into bin/.

    The name is the contract: anything starting with `set-memory` or `set-hook-memory`
    is the removed subsystem, whatever it contains.
    """
    offenders = sorted(
        p.name
        for p in (REPO / "bin").iterdir()
        if p.is_file() and p.name.startswith(FORBIDDEN_BIN_PREFIXES)
    )
    assert offenders == [], (
        f"bin/ contains removed memory executables: {offenders}. "
        "The memory subsystem was removed; see openspec/changes/remove-shodh-memory."
    )


def _first_party_python_files() -> list[Path]:
    roots = [REPO / "lib", REPO / "mcp-server", REPO / "modules"]
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if "__pycache__" in p.parts or "/tests/" in str(p):
                continue
            out.append(p)
    return out


def test_no_first_party_module_imports_the_removed_packages():
    """A failure here means an import was re-linked.

    Matched at the start of a line so a mention inside a docstring or a comment — of
    which there are several deliberate historical ones — does not trip it. This is the
    check that would catch a partially-restored subsystem, where the executable is still
    absent but the library came back.
    """
    pattern = re.compile(
        r"^\s*(?:import|from)\s+(" + "|".join(FORBIDDEN_IMPORTS) + r")\b", re.M
    )
    offenders: list[str] = []
    for path in _first_party_python_files():
        text = path.read_text(errors="replace")
        for m in pattern.finditer(text):
            line = text[: m.start()].count("\n") + 1
            offenders.append(f"{path.relative_to(REPO)}:{line} -> {m.group(1)}")

    assert offenders == [], (
        "first-party modules import removed memory packages:\n  "
        + "\n  ".join(offenders)
    )

    # The corpus must be non-empty, or this test proves nothing. Measured at the time of
    # writing: several hundred files. A zero here means the collector broke, not that the
    # tree is clean — the same reassuring-empty shape that let the subsystem stay broken
    # for six months.
    assert len(_first_party_python_files()) > 50


def test_no_shell_script_invokes_the_removed_commands():
    """A failure here means a caller came back.

    `lib/project/deploy.sh` is exempt on purpose: it DETECTS and removes leftovers from a
    consumer tree, so it must keep naming the strings it cleans up. Exempting it by path
    rather than by pattern keeps the exemption visible.
    """
    exempt = {"lib/project/deploy.sh"}
    pattern = re.compile(r"(?<![\w-])(set-memory|set-memoryd|set-memory-hooks)(?![\w-])")
    offenders: list[str] = []
    for root in ("bin", "lib", "modules"):
        base = REPO / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in ("", ".sh"):
                continue
            rel = str(path.relative_to(REPO))
            if rel in exempt:
                continue
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            for m in pattern.finditer(text):
                line = text[: m.start()].count("\n") + 1
                offenders.append(f"{rel}:{line} -> {m.group(1)}")

    assert offenders == [], (
        "shell scripts still invoke removed memory commands:\n  " + "\n  ".join(offenders)
    )


def test_the_mcp_server_registers_no_memory_tool():
    """A failure here means a tool came back onto the MCP surface.

    Read from the AST rather than from a running server: `fastmcp` is not installed on
    every machine this suite runs on, so importing the module is not available as a check.
    That is a weaker measurement than asking the registry, and saying so is the point.
    """
    import ast

    src = (REPO / "mcp-server" / "set_mcp_server.py").read_text()
    tree = ast.parse(src)
    registered: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if "tool" in ast.dump(dec):
                    registered.add(node.name)

    memory_tools = {
        "remember", "recall", "recall_by_date", "proactive_context", "forget",
        "forget_by_tags", "list_memories", "get_memory", "context_summary", "brain",
        "memory_stats", "memory_health", "audit", "cleanup", "dedup", "verify_index",
        "consolidation_report", "graph_stats", "sync", "sync_push", "sync_pull",
        "sync_status", "export_memories", "import_memories",
        "add_todo", "list_todos", "complete_todo",
    }

    assert registered & memory_tools == set(), (
        f"MCP server registers removed memory tools: {sorted(registered & memory_tools)}"
    )
    # Guard the guard: if the AST walk found nothing at all, the assertion above is
    # vacuous and would stay green through any change to the file.
    assert len(registered) >= 5, f"expected the surviving tools, found {sorted(registered)}"


@pytest.mark.skipif(
    subprocess.run(["which", "jq"], capture_output=True).returncode != 0,
    reason="set-deploy-hooks requires jq",
)
def test_a_deploy_produces_no_memory_hook_and_strips_the_ones_it_finds():
    """A failure here means the reinstall path reopened.

    Two directions in one test, because they fail differently: a fresh deploy must not
    ADD a memory hook, and a deploy onto a config that already carries nine must REMOVE
    them without being asked. The second is what cleans a project restored from a backup.
    """
    deploy = REPO / "bin" / "set-deploy-hooks"

    def count_memory_hooks(settings: Path) -> tuple[int, int]:
        data = json.loads(settings.read_text())
        mem = other = 0
        for _event, groups in (data.get("hooks") or {}).items():
            for group in groups:
                for hook in group.get("hooks", []):
                    if hook.get("command", "").startswith("set-hook-memory"):
                        mem += 1
                    else:
                        other += 1
        return mem, other

    with tempfile.TemporaryDirectory() as tmp:
        # (a) fresh deploy
        fresh = Path(tmp) / "fresh"
        fresh.mkdir()
        subprocess.run([str(deploy), "--quiet", str(fresh)], check=True,
                       capture_output=True, timeout=60)
        settings = fresh / ".claude" / "settings.json"
        assert settings.is_file()
        mem, other = count_memory_hooks(settings)
        assert mem == 0, "a fresh deploy installed memory hooks"
        assert other > 0, "a fresh deploy installed nothing at all"

        # (b) deploy onto a config carrying memory hooks AND the project's own
        dirty = Path(tmp) / "dirty"
        (dirty / ".claude").mkdir(parents=True)
        seeded = {
            "hooks": {
                "SessionStart": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "set-hook-memory SessionStart"}]}],
                "PostToolUse": [
                    {"matcher": "Read", "hooks": [
                        {"type": "command", "command": "set-hook-memory PostToolUse"}]},
                    {"matcher": "Bash", "hooks": [
                        {"type": "command", "command": "set-hook-memory PostToolUse"},
                        {"type": "command", "command": "my-own-project-hook"}]},
                ],
            }
        }
        (dirty / ".claude" / "settings.json").write_text(json.dumps(seeded, indent=2))
        before_mem, before_other = count_memory_hooks(dirty / ".claude" / "settings.json")
        assert (before_mem, before_other) == (3, 1)

        subprocess.run([str(deploy), "--quiet", str(dirty)], check=True,
                       capture_output=True, timeout=60)
        after_mem, after_other = count_memory_hooks(dirty / ".claude" / "settings.json")
        assert after_mem == 0, "a deploy left memory hooks in place"
        # The project's own hook survives, and the framework's own are added alongside.
        text = (dirty / ".claude" / "settings.json").read_text()
        assert "my-own-project-hook" in text, "the deploy discarded the project's own hook"
