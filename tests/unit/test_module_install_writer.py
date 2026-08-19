"""`install_module` — the guard and the report around a write that already existed.

The write was never missing: `profile_deploy` has copied a module's declared files, ledgered
them and announced them for a long time. What was missing, measured 2026-08-19 and all three
at zero occurrences in `lib/`, was every *account* of it — `InstallReport` constructed nowhere,
`check_requirements` called nowhere, `plan_files` called nowhere.

So the tests here are about the unhappy paths, because the happy one was already working and
is not where the defects are. Each one is a case a demo never reaches.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from set_orch.module_declaration import load_declaration
from set_orch.module_install import (
    INSTALL_RECORD_REL, InstallRefused, install_module, read_install_record,
)


def _module(tmp_path: Path, name: str, manifest: dict, files: dict) -> tuple:
    tpl = tmp_path / name
    for rel, body in files.items():
        (tpl / rel).parent.mkdir(parents=True, exist_ok=True)
        (tpl / rel).write_text(body, encoding="utf-8")
    (tpl / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    decl = load_declaration(manifest, name=name, source=tpl / "manifest.yaml")
    return decl, tpl


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "set").mkdir(parents=True)
    return root


def _tree_hash(root: Path) -> dict:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


# ── the happy path, only far enough to make the unhappy ones mean something ───────────────

def test_the_declared_files_are_written_and_every_one_is_named(tmp_path):
    decl, _ = _module(
        tmp_path, "alpha",
        {"version": "1.0.0", "core": [{"path": "a.md", "replace": True},
                                      {"path": "docs/b.md", "replace": True}]},
        {"a.md": "A\n", "docs/b.md": "B\n"},
    )
    root = _project(tmp_path)
    report = install_module(decl, root)

    assert (root / "a.md").read_text() == "A\n"
    assert (root / "docs" / "b.md").read_text() == "B\n"
    assert sorted(report.written) == ["a.md", "docs/b.md"]
    assert report.changed_nothing is False


# ── refusal ───────────────────────────────────────────────────────────────────────────────

def test_a_module_whose_requirement_is_absent_is_refused_and_the_requirement_is_named(tmp_path):
    decl, _ = _module(
        tmp_path, "beta",
        {"version": "1.0.0", "requires": ["alpha"],
         "core": [{"path": "b.md", "replace": True}]},
        {"b.md": "B\n"},
    )
    root = _project(tmp_path)
    with pytest.raises(InstallRefused) as excinfo:
        install_module(decl, root)
    assert "alpha" in str(excinfo.value)


def test_the_refusal_precedes_the_first_write(tmp_path):
    """The half that matters. A refusal after one file is the same failure with extra
    steps, and it leaves a project half-installed by a run that reported an error."""
    decl, _ = _module(
        tmp_path, "beta",
        {"version": "1.0.0", "requires": ["alpha"],
         "core": [{"path": "first.md", "replace": True},
                  {"path": "second.md", "replace": True}]},
        {"first.md": "1\n", "second.md": "2\n"},
    )
    root = _project(tmp_path)
    before = _tree_hash(root)
    with pytest.raises(InstallRefused):
        install_module(decl, root)
    assert not (root / "first.md").exists(), "the FIRST planned file was written before refusing"
    assert _tree_hash(root) == before, "a refused install changed the project"


def test_a_satisfied_requirement_does_not_block(tmp_path):
    """The other direction. A guard that never lets anything through is not a guard."""
    decl, _ = _module(
        tmp_path, "beta",
        {"version": "1.0.0", "requires": ["alpha"],
         "core": [{"path": "b.md", "replace": True}]},
        {"b.md": "B\n"},
    )
    root = _project(tmp_path)
    (root / INSTALL_RECORD_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / INSTALL_RECORD_REL).write_text(
        json.dumps({"modules": {"alpha": "1.0.0"}, "announcements": {}}), encoding="utf-8")
    assert install_module(decl, root).written == ["b.md"]


def test_a_refused_install_leaves_the_record_alone(tmp_path):
    decl, _ = _module(
        tmp_path, "beta",
        {"version": "1.0.0", "requires": ["gamma"], "core": [{"path": "b.md", "replace": True}]},
        {"b.md": "B\n"},
    )
    root = _project(tmp_path)
    (root / INSTALL_RECORD_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / INSTALL_RECORD_REL).write_text(
        json.dumps({"modules": {"alpha": "1.0.0"}, "announcements": {}}), encoding="utf-8")
    before = (root / INSTALL_RECORD_REL).read_bytes()

    with pytest.raises(InstallRefused):
        install_module(decl, root)
    assert (root / INSTALL_RECORD_REL).read_bytes() == before
    assert "beta" not in read_install_record(root).modules


# ── the record ────────────────────────────────────────────────────────────────────────────

def test_a_module_with_no_announcement_is_still_recorded(tmp_path):
    """The measured bug this change exists downstream of.

    The only `record.save()` on the deploy path sat inside `if decl.announce is not None`,
    so a module with no announcement installed its files and left NO trace that it had —
    which is why the capability report has to infer from file presence, and why the fleet
    screen measured no declaration across three real projects.

    A test suite whose every fixture announces would pass on the broken build. This one
    deliberately declares no announcement.
    """
    decl, _ = _module(
        tmp_path, "quiet",
        {"version": "2.1.0", "core": [{"path": "q.md", "replace": True}]},
        {"q.md": "Q\n"},
    )
    root = _project(tmp_path)
    install_module(decl, root)
    assert read_install_record(root).modules == {"quiet": "2.1.0"}


def test_a_dry_run_records_nothing_and_writes_nothing(tmp_path):
    """Asserted by hashing the tree, not by trusting the flag."""
    decl, _ = _module(
        tmp_path, "alpha",
        {"version": "1.0.0", "core": [{"path": "a.md", "replace": True}]},
        {"a.md": "A\n"},
    )
    root = _project(tmp_path)
    before = _tree_hash(root)
    report = install_module(decl, root, dry_run=True)
    assert _tree_hash(root) == before, "a dry run touched the project"
    assert report.written == ["a.md"], "a dry run must still say what it WOULD write"
    assert read_install_record(root).modules == {}


# ── what it did not do ────────────────────────────────────────────────────────────────────

def test_a_file_the_project_edited_is_skipped_with_its_reason_and_left_byte_identical(tmp_path):
    decl, _ = _module(
        tmp_path, "alpha",
        {"version": "1.0.0", "core": [{"path": "rules/r.md", "protected": True}]},
        {"rules/r.md": "from the template\n"},
    )
    root = _project(tmp_path)
    (root / ".claude" / "rules").mkdir(parents=True)
    edited = root / ".claude" / "rules" / "r.md"
    edited.write_text("the project edited this\n", encoding="utf-8")
    before = hashlib.sha256(edited.read_bytes()).hexdigest()

    report = install_module(decl, root)

    assert hashlib.sha256(edited.read_bytes()).hexdigest() == before
    assert report.written == []
    assert [(s.path, s.reason) for s in report.skipped] == [(".claude/rules/r.md", "protected")]


def test_an_install_that_skipped_everything_says_it_changed_nothing(tmp_path):
    decl, _ = _module(
        tmp_path, "alpha",
        {"version": "1.0.0", "core": [{"path": "rules/r.md", "protected": True}]},
        {"rules/r.md": "from the template\n"},
    )
    root = _project(tmp_path)
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "rules" / "r.md").write_text("mine\n", encoding="utf-8")

    report = install_module(decl, root)
    assert report.changed_nothing is True
    assert any("wrote no files" in line for line in report.as_lines())
    assert any("protected" in line for line in report.as_lines())


def test_the_report_names_both_halves_when_it_wrote_some_and_skipped_others(tmp_path):
    """Neither half may be inferable only from the other's absence."""
    decl, _ = _module(
        tmp_path, "alpha",
        {"version": "1.0.0", "core": [{"path": "new.md", "replace": True},
                                      {"path": "rules/r.md", "protected": True}]},
        {"new.md": "N\n", "rules/r.md": "template\n"},
    )
    root = _project(tmp_path)
    (root / ".claude" / "rules").mkdir(parents=True)
    (root / ".claude" / "rules" / "r.md").write_text("mine\n", encoding="utf-8")

    report = install_module(decl, root)
    assert report.written == ["new.md"]
    assert [s.path for s in report.skipped] == [".claude/rules/r.md"]
    lines = "\n".join(report.as_lines())
    assert "wrote    new.md" in lines and "skipped  .claude/rules/r.md" in lines


# ── the executable part ───────────────────────────────────────────────────────────────────

def test_a_manifest_that_declares_a_path_as_both_is_refused_by_the_deploy_path(tmp_path):
    """⚠ This test replaces one that asserted the WRONG guarantee, and the correction is
    the useful half.

    The first version asserted that a path declared both as an installed file and as the
    module's executable part would be silently pruned from the plan — and a change was
    written to make the deploy parser do that pruning. Measured while the test failed:
    `validate_declaration` runs **before** the file list is built and **refuses** such a
    manifest outright (`guard-cannot-be-applied`). So the only input that could separate
    the two manifest readers never reaches the second one, the divergence claimed in the
    design does not exist on any reachable path, and the pruning code would have been
    unreachable code claiming to be a guard — the same shape as a manifest declaring a
    protection nothing reads, which this repository has already paid for.

    What is actually guaranteed is a refusal, and a refusal is stronger than an exclusion:
    it stops the install rather than quietly installing a subset.
    """
    from set_orch.profile_deploy import ManifestValidationError
    decl, _ = _module(
        tmp_path, "alpha",
        {"version": "1.0.0", "executable": ["bin/engine"],
         "core": [{"path": "a.md", "replace": True},
                  {"path": "bin/engine", "replace": True}]},
        {"a.md": "A\n", "bin/engine": "#!/bin/sh\n"},
    )
    root = _project(tmp_path)
    with pytest.raises(ManifestValidationError) as excinfo:
        install_module(decl, root)
    assert "executable" in str(excinfo.value)
    assert not (root / "bin" / "engine").exists()
    assert not (root / "a.md").exists(), "the refusal came after writing a file"


def test_an_executable_declared_without_being_an_installed_file_is_simply_not_planned(tmp_path):
    """The valid spelling, and the one a real module uses: the executable is named so the
    declaration can say what it ships, and it is not among `core`. Nothing has to exclude
    it, because nothing ever plans it — which is what "structural" means here.
    """
    from set_orch.module_install import plan_files
    decl, _ = _module(
        tmp_path, "alpha",
        {"version": "1.0.0", "executable": ["bin/engine"],
         "core": [{"path": "a.md", "replace": True}]},
        {"a.md": "A\n", "bin/engine": "#!/bin/sh\n"},
    )
    assert plan_files(decl) == ["a.md"]
    root = _project(tmp_path)
    report = install_module(decl, root)
    assert report.written == ["a.md"]
    assert not (root / "bin" / "engine").exists()


# ── locating the module's files ───────────────────────────────────────────────────────────

def test_a_module_whose_files_cannot_be_found_is_refused_not_reported_as_empty(tmp_path):
    """An install that writes nothing because it could not find anything to write is not a
    run that changed nothing — it is a run that did not happen, and the two must not read
    the same. This is the false-absence class applied to an install."""
    from set_orch.module_declaration import load_declaration as _load
    decl = _load({"version": "1.0.0", "core": []}, name="ghost", source=None)
    with pytest.raises(InstallRefused) as excinfo:
        install_module(decl, _project(tmp_path))
    assert "cannot locate" in str(excinfo.value)


def test_a_file_already_byte_identical_is_reported_as_unchanged_not_as_written(tmp_path):
    """Added after a mutation run, and the mutation had to be re-aimed twice.

    Removing the `unchanged` branch outright changes nothing — it falls through to the
    `else`, which produces the identical skip. That is an *equivalent mutant*: the code is
    explicit rather than load-bearing, and a loop reporting it as NOT CAUGHT is accusing a
    test of weakness for a change that has no effect. The hazard this test actually guards
    is the opposite edit — folding `unchanged` in with `deployed` — and that one is caught.

    The distinction matters in both directions. Calling a byte-identical no-op a *write*
    makes a report of "12 files written" out of a run that changed nothing — and a reader
    deciding whether to look at a diff believes it. Saying nothing at all would be the
    silent half: "this file was already what the module ships" is exactly what someone
    asking why a capability still reads not-connected needs to be told.
    """
    decl, tpl = _module(
        tmp_path, "alpha",
        {"version": "1.0.0", "core": [{"path": "a.md", "replace": True}]},
        {"a.md": "A\n"},
    )
    root = _project(tmp_path)
    (root / "a.md").write_text("A\n", encoding="utf-8")     # already identical

    report = install_module(decl, root)
    assert report.written == [], "a byte-identical no-op was reported as a write"
    assert [(s.path, s.reason) for s in report.skipped] == [("a.md", "identical")]
    assert report.changed_nothing is True
