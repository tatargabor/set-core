"""Scaffold (`once: true`) vs knowledge files in template deployment.

Two kinds of file live in a template and want opposite treatment once a project
is real. Scaffold is starter code the project outgrows: present means done.
Knowledge is the framework's own rules, which SHOULD keep flowing to untouched
files, or a fix never reaches the projects that need it.

The third case pinned down here is reporting: a byte-identical rewrite must not
be announced as an overwrite. A plan that overstates its own blast radius is a
plan nobody trusts, and an untrusted plan does not get read.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.profile_deploy import (  # noqa: E402
    _parse_file_entry,
    _deploy_single_template,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture
def trees(tmp_path):
    template = tmp_path / "template"
    target = tmp_path / "project"
    template.mkdir()
    target.mkdir()
    return template, target


def _manifest(template: Path, entries: str) -> None:
    # A declaration states its own version and a treatment per file; the installer now
    # refuses one that does not, so a fixture must be a valid declaration too.
    _write(template / "manifest.yaml", 'version: "test"\ncore:\n' + entries)


def _deploy(template, target, *, dry_run=False):
    return _deploy_single_template(template, target, force=True, dry_run=dry_run)


# ── parsing ────────────────────────────────────────────────────────────────

def test_once_flag_parses_from_manifest_entry():
    assert _parse_file_entry({"path": "a.ts", "once": True}).once is True


def test_once_defaults_false_for_plain_string_entries():
    assert _parse_file_entry("a.ts").once is False


def test_once_defaults_false_when_flag_absent():
    assert _parse_file_entry({"path": "a.ts", "protected": True}).once is False


# ── scaffold: present means done ───────────────────────────────────────────

def test_scaffold_is_not_redeployed_when_present_and_edited(trees):
    template, target = trees
    _write(template / "prisma.ts", "template version\n")
    _manifest(template, "  - path: prisma.ts\n    once: true\n")
    _write(target / "prisma.ts", "the project's own version\n")

    _deploy(template, target)

    assert (target / "prisma.ts").read_text() == "the project's own version\n"


def test_scaffold_is_not_rewritten_even_when_byte_identical(trees):
    """`once` does not ask whether the file was edited — present is done.

    This is what separates it from `protected`, which skips only on difference
    and would rewrite an untouched scaffold on every single init.
    """
    template, target = trees
    _write(template / "eslint.config.mjs", "same\n")
    _manifest(template, "  - path: eslint.config.mjs\n    once: true\n")
    dst = _write(target / "eslint.config.mjs", "same\n")
    before = dst.stat().st_mtime_ns

    msgs = _deploy(template, target)

    assert dst.stat().st_mtime_ns == before, "scaffold was rewritten"
    assert any("scaffold, already present" in m for m in msgs)


def test_scaffold_is_deployed_when_absent(trees):
    """A new project still gets its starter code — `once` is not `never`."""
    template, target = trees
    _write(template / "prisma.ts", "template version\n")
    _manifest(template, "  - path: prisma.ts\n    once: true\n")

    _deploy(template, target)

    assert (target / "prisma.ts").read_text() == "template version\n"


# ── knowledge: keeps flowing when untouched ────────────────────────────────

def test_untouched_knowledge_file_still_updates(trees):
    """The regression `once` must NOT introduce for rules.

    If knowledge stopped flowing, every fix the framework learns would stall at
    the first project that already holds the old copy.
    """
    template, target = trees
    _write(template / "rules" / "web.md", "v2 improved\n")
    _manifest(template, "  - path: rules/web.md\n    protected: true\n")
    _write(target / ".claude" / "rules" / "web.md", "v2 improved\n")

    _deploy(template, target)

    assert (target / ".claude" / "rules" / "web.md").read_text() == "v2 improved\n"


def test_edited_knowledge_file_is_preserved(trees):
    template, target = trees
    _write(template / "rules" / "web.md", "framework version\n")
    _manifest(template, "  - path: rules/web.md\n    protected: true\n")
    _write(target / ".claude" / "rules" / "web.md", "project's tuned version\n")

    msgs = _deploy(template, target)

    assert (target / ".claude" / "rules" / "web.md").read_text() == "project's tuned version\n"
    assert any("protected" in m for m in msgs)


# ── reporting ──────────────────────────────────────────────────────────────

def test_identical_content_reports_unchanged_not_overwrite(trees):
    template, target = trees
    _write(template / "rules" / "web.md", "identical\n")
    _manifest(template, "  - path: rules/web.md\n    protected: true\n")
    _write(target / ".claude" / "rules" / "web.md", "identical\n")

    msgs = _deploy(template, target, dry_run=True)

    joined = "\n".join(msgs)
    assert "Unchanged (identical)" in joined
    assert "overwrite" not in joined.lower(), "a no-op was reported as data loss"


def test_differing_file_still_reports_overwrite(trees):
    """The honest case must keep saying 'overwrite' — this one is a real rewrite."""
    template, target = trees
    _write(template / "notes.md", "new\n")
    _manifest(template, "  - path: notes.md\n    replace: true\n")
    _write(target / "notes.md", "old\n")

    msgs = _deploy(template, target, dry_run=True)

    assert any("overwrite" in m.lower() for m in msgs)


def test_dry_run_writes_nothing_for_any_flag_combination(trees):
    template, target = trees
    _write(template / "prisma.ts", "template\n")
    _write(template / "rules" / "web.md", "framework\n")
    _manifest(
        template,
        "  - path: prisma.ts\n    once: true\n"
        "  - path: rules/web.md\n    protected: true\n",
    )
    _write(target / "prisma.ts", "project\n")

    _deploy(template, target, dry_run=True)

    assert (target / "prisma.ts").read_text() == "project\n"
    assert not (target / ".claude" / "rules" / "web.md").exists()
