"""Module install: what a module declares, what an installer refuses, and what it says.

Written with the change `work-cycle-engine-apply-first`, group 1. The governing rule these
tests encode is that **a declared guard which does not take effect is worse than no guard** —
it has already happened in this repository, where two templates named protected paths in a
top-level list that nothing read, and a forced re-init overwrote the file the manifest claimed
to protect.

Task 1.9 asked for an audit of the shipped manifests. It is a **test** rather than a report,
because a report is true on the day it is written and a test refuses to be reverted.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lib"))

from set_orch.deploy_ledger import DeployLedger, tombstoned_paths  # noqa: E402
from set_orch.module_announce import (  # noqa: E402
    announce_module,
    read_section,
    section_markers,
    withdraw_announcement,
)
from set_orch.module_declaration import (  # noqa: E402
    E_CONTRADICTORY_GUARDS,
    E_GUARD_INAPPLICABLE,
    E_NO_TREATMENT,
    E_NO_VERSION,
    E_UNKNOWN_GUARD,
    FileDeclaration,
    ModuleDeclaration,
    check_requirements,
    compare_generator_stamps,
    compare_versions,
    load_declaration,
    read_generator_stamp,
    validate_declaration,
)
from set_orch.module_install import (  # noqa: E402
    InstallRecord,
    InstallReport,
    ProjectDeclaration,
    plan_files,
    read_install_record,
    read_project_declaration,
    version_report,
)

SHIPPED_MANIFESTS = sorted(
    glob.glob(str(REPO / "modules/*/set_project_*/templates/*/manifest.yaml"))
)


def _codes(errors) -> set[str]:
    return {e.code for e in errors}


# ── 1.9 — the audit, held as a test ───────────────────────────────────────────────────────


def test_there_are_shipped_manifests_to_audit():
    """Guard the guard: an empty corpus would make every audit below pass vacuously."""
    assert len(SHIPPED_MANIFESTS) >= 3, SHIPPED_MANIFESTS


@pytest.mark.parametrize("manifest_path", SHIPPED_MANIFESTS, ids=lambda p: Path(p).parts[-4])
def test_every_shipped_manifest_states_a_treatment_for_every_file_it_declares(manifest_path):
    """The audit task 1.9 asked for, in the only form that survives the next edit.

    Optional module sections are included, not just `core` — an entry that only appears when
    a module is selected is exactly the one an audit of the default path would miss.
    """
    path = Path(manifest_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    decl = load_declaration(
        raw, name=path.parts[-4], source=path, modules=list((raw.get("modules") or {}).keys()),
    )
    errors = validate_declaration(decl, template_dir=path.parent)
    assert errors == [], "\n".join(str(e) for e in errors)


# ── the executable / project-owned split ──────────────────────────────────────────────────


def test_the_executable_part_is_not_copied_into_a_project():
    decl = ModuleDeclaration(
        name="wc", version="0.1.0",
        files=[FileDeclaration("set/modules.yaml", frozenset({"protected"})),
               FileDeclaration("bin/engine", frozenset({"replace"}))],
        executable=("bin/engine",),
    )
    assert plan_files(decl) == ["set/modules.yaml"]


def test_the_engine_is_invoked_from_the_machine_wide_installation(tmp_path):
    """The scenario's second half, which the plan-level test above does not reach.

    `plan_files` proves the executable is not COPIED. That a project can still run it is a
    separate claim, and it rests on the entry point being installed machine-wide rather than
    per project. Read from `pyproject.toml` so a rename or a removal fails here instead of
    at a consumer's shell prompt.
    """
    import tomllib
    root = Path(__file__).resolve().parents[2]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]
    assert scripts["set-work-cycle"] == "set_workcycle.cli:main"
    # And nothing ships it as an installed file into a project tree.
    for manifest in SHIPPED_MANIFESTS:
        raw = yaml.safe_load(Path(manifest).read_text(encoding="utf-8")) or {}
        entries = [e if isinstance(e, str) else (e or {}).get("path", "")
                   for section in raw.values() if isinstance(section, list) for e in section]
        assert not any(str(e).startswith("bin/") for e in entries), manifest


def test_declaring_a_path_as_both_executable_and_installed_is_an_error():
    """The exclusion in `plan_files` is a safety net; the declaration is where it is caught."""
    decl = ModuleDeclaration(
        name="wc", version="0.1.0",
        files=[FileDeclaration("bin/engine", frozenset({"replace"}))],
        executable=("bin/engine",),
    )
    assert E_GUARD_INAPPLICABLE in _codes(validate_declaration(decl))


def test_runtime_state_is_not_an_install_artifact(tmp_path):
    """An install neither creates nor removes a lock, a run record or a pending answer."""
    (tmp_path / "set" / "runtime").mkdir(parents=True)
    lock = tmp_path / "set" / "runtime" / "unit.lock"
    lock.write_text("held by session-abc", encoding="utf-8")

    record = InstallRecord(modules={"wc": "0.1.0"})
    record.save(tmp_path)

    assert lock.read_text(encoding="utf-8") == "held by session-abc"
    assert "set/runtime/unit.lock" not in json.dumps(
        json.loads((tmp_path / "set/.installed-modules.json").read_text())
    )


# ── the declaration, and what validation refuses ──────────────────────────────────────────


def test_a_file_entry_with_no_treatment_stated_is_refused_not_defaulted():
    decl = load_declaration({"core": ["a.md"], "version": "1.0"}, name="m")
    errors = validate_declaration(decl)
    assert E_NO_TREATMENT in _codes(errors)
    assert any(e.path == "a.md" for e in errors), "the refusal names the file"


def test_a_complete_declaration_validates():
    decl = load_declaration(
        {"version": "1.0", "core": [{"path": "a.md", "protected": True}]}, name="m")
    assert validate_declaration(decl) == []


def test_a_path_named_in_the_top_level_protected_list_states_a_treatment():
    """Both manifest spellings mean the same thing. Refusing the terser one would reject two
    templates that are protecting their files correctly."""
    decl = load_declaration(
        {"version": "1.0", "core": ["a.md"], "protected": ["a.md"]}, name="m")
    assert validate_declaration(decl) == []


def test_replace_is_how_a_declaration_says_no_guard():
    decl = load_declaration({"version": "1.0", "core": [{"path": "a.md", "replace": True}]},
                            name="m")
    assert validate_declaration(decl) == []


def test_a_module_with_no_version_is_refused():
    decl = load_declaration({"core": [{"path": "a.md", "once": True}]}, name="m")
    assert E_NO_VERSION in _codes(validate_declaration(decl))


def test_an_unrecognised_guard_fails_the_install_and_is_named():
    decl = load_declaration(
        {"version": "1.0", "core": [{"path": "a.md", "encrypted": True}]}, name="m")
    errors = validate_declaration(decl)
    assert E_UNKNOWN_GUARD in _codes(errors)
    assert any("encrypted" in e.message for e in errors)


def test_a_guard_that_cannot_be_applied_fails_for_that_file(tmp_path):
    """`merge` on a file the module does not ship is a guard that will never take effect."""
    decl = load_declaration(
        {"version": "1.0", "core": [{"path": "absent.yaml", "merge": True}]}, name="m")
    errors = validate_declaration(decl, template_dir=tmp_path)
    assert E_GUARD_INAPPLICABLE in _codes(errors)
    (tmp_path / "absent.yaml").write_text("x", encoding="utf-8")
    assert validate_declaration(decl, template_dir=tmp_path) == []


def test_replace_beside_a_guard_is_a_contradiction():
    decl = load_declaration(
        {"version": "1.0", "core": [{"path": "a.md", "replace": True, "protected": True}]},
        name="m")
    assert E_CONTRADICTORY_GUARDS in _codes(validate_declaration(decl))


# ── requirements ──────────────────────────────────────────────────────────────────────────


def test_a_missing_required_module_refuses_the_install_and_names_it():
    decl = ModuleDeclaration(name="wc", version="0.1.0", requires=("web",))
    errors = check_requirements(decl, installed=["example"])
    assert len(errors) == 1 and "web" in errors[0].message


def test_satisfied_requirements_do_not_block():
    decl = ModuleDeclaration(name="wc", version="0.1.0", requires=("web",))
    assert check_requirements(decl, installed=["web", "example"]) == []


# ── versions ──────────────────────────────────────────────────────────────────────────────


def test_a_version_mismatch_is_reported_naming_both():
    c = compare_versions("wc", expected="0.1.0", installed="0.2.0")
    assert c.state == "mismatch"
    assert "0.1.0" in c.describe() and "0.2.0" in c.describe()


@pytest.mark.parametrize("expected,installed", [(None, "0.2.0"), ("0.1.0", None), (None, None)])
def test_an_unreadable_version_is_unknown_and_never_a_match(expected, installed):
    """The fail direction: rendering 'cannot tell' as 'fine' removes the answer being sought."""
    c = compare_versions("wc", expected=expected, installed=installed)
    assert c.state == "unknown"
    assert "unknown" in c.describe()


def test_version_report_covers_what_the_project_asked_for_and_what_is_installed():
    project = ProjectDeclaration(wants={"wc": "0.1.0", "web": "2.0"}, present=True)
    states = {c.module: c.state for c in version_report(project, {"wc": "0.1.0"})}
    assert states == {"wc": "match", "web": "unknown"}


# ── generator stamps ──────────────────────────────────────────────────────────────────────


def test_an_older_generator_s_output_does_not_replace_a_newer_artifact():
    c = compare_generator_stamps("s.md", destination_stamp="1.9.0", incoming_stamp="1.1.1")
    assert c.verdict == "refuse"
    assert "1.9.0" in c.reason and "1.1.1" in c.reason, "the refusal reports both versions"


def test_a_newer_incoming_artifact_may_replace_an_older_one():
    assert compare_generator_stamps("s.md", "1.1.1", "1.9.0").verdict == "replace"


@pytest.mark.parametrize("dest,inc", [(None, "1.9.0"), ("1.9.0", None), (None, None)])
def test_a_missing_stamp_on_either_side_leaves_the_destination_alone(dest, inc):
    assert compare_generator_stamps("s.md", dest, inc).verdict == "unknown"


def test_a_stamp_is_read_from_front_matter_not_from_prose(tmp_path):
    """Anchored at line start and near the top: a version *mentioned* in a sentence is not a
    stamp. Reading prose as a value is a defect class this repository has paid for."""
    stamped = tmp_path / "a.md"
    stamped.write_text('name: skill\ngeneratedBy: "1.9.0"\n\nbody\n', encoding="utf-8")
    assert read_generator_stamp(stamped) == "1.9.0"

    mention = tmp_path / "b.md"
    mention.write_text("Some text explaining that `generatedBy: 1.1.1` used to appear.\n",
                       encoding="utf-8")
    assert read_generator_stamp(mention) is None


# ── provenance, skips, deletion ───────────────────────────────────────────────────────────


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "set").mkdir(parents=True)
    return root


def test_an_installed_file_the_project_edited_is_left_alone_and_the_skip_says_why(tmp_path):
    """Task 1.10's named case, end to end: edit an installed file, install again, and the run
    must both leave it alone and NAME it. A silent skip is the same class as a silent
    overwrite — both leave a state nobody chose."""
    root = _project(tmp_path)
    src = tmp_path / "template.md"
    src.write_text("from the template\n", encoding="utf-8")
    dst = root / "a.md"
    dst.write_text("from the template\n", encoding="utf-8")

    ledger = DeployLedger.load(root)
    key = ledger.rel_key(dst)
    ledger.record(key, src)
    ledger.save()

    assert DeployLedger.load(root).decide(key, dst)[0] is True, "untouched may be updated"

    dst.write_text("the project edited this\n", encoding="utf-8")
    ok, reason = DeployLedger.load(root).decide(key, dst)
    assert ok is False
    assert "modified" in reason

    report = InstallReport(module="m")
    report.skip(key, reason)
    lines = "\n".join(report.as_lines())
    assert key in lines and "modified" in lines
    assert dst.read_text(encoding="utf-8") == "the project edited this\n"


def test_a_seed_time_equality_does_not_stand_in_for_a_current_hash(tmp_path):
    """Identical at first install, diverged since — the divergence is what decides, not the
    fact that the two were once the same."""
    root = _project(tmp_path)
    src = tmp_path / "t.md"
    src.write_text("same\n", encoding="utf-8")
    dst = root / "b.md"
    dst.write_text("same\n", encoding="utf-8")
    ledger = DeployLedger.load(root)
    key = ledger.rel_key(dst)
    ledger.record(key, src)
    dst.write_text("same\nplus a project line\n", encoding="utf-8")
    ok, reason = ledger.decide(key, dst)
    assert ok is False and "modified" in reason


def test_a_file_of_unknown_provenance_is_left_alone(tmp_path):
    root = _project(tmp_path)
    dst = root / "c.md"
    dst.write_text("who wrote this\n", encoding="utf-8")
    ok, reason = DeployLedger.load(root).decide("c.md", dst)
    assert ok is False and "unknown provenance" in reason


def test_a_removed_file_stays_removed_and_the_removal_is_listable(tmp_path):
    root = _project(tmp_path)
    src = tmp_path / "t.md"
    src.write_text("x\n", encoding="utf-8")
    dst = root / "d.md"
    dst.write_text("x\n", encoding="utf-8")

    ledger = DeployLedger.load(root)
    key = ledger.rel_key(dst)
    ledger.record(key, src)
    ledger.save()

    dst.unlink()
    ledger = DeployLedger.load(root)
    ok, reason = ledger.decide(key, dst)
    assert ok is False and "tombstone" in reason
    ledger.save()

    again = DeployLedger.load(root)
    assert again.decide(key, dst)[0] is False, "the removal survives a later install"
    assert key in tombstoned_paths(root), "recorded removals are listable"


def test_an_install_that_wrote_nothing_says_so_explicitly(tmp_path):
    report = InstallReport(module="m")
    report.skip("a.md", "modified by the project")
    assert report.changed_nothing is True
    assert any("wrote no files" in line for line in report.as_lines())

    report.wrote("b.md")
    assert report.changed_nothing is False
    assert not any("wrote no files" in line for line in report.as_lines())


# ── what a project asked for ──────────────────────────────────────────────────────────────


def test_only_the_modules_a_project_asked_for_are_installed(tmp_path):
    root = _project(tmp_path)
    (root / "set" / "modules.yaml").write_text(
        "modules:\n  web:\n    version: '0.2.0'\n", encoding="utf-8")
    decl = read_project_declaration(root)
    assert decl.present is True
    assert decl.asked_for("web") is True
    assert decl.asked_for("mobile") is False


def test_an_absent_project_declaration_is_reported_as_absent_not_as_empty(tmp_path):
    """'Not adopted' and 'adopted and wants nothing' are different states, and a reader must
    not be able to take the first for the second."""
    decl = read_project_declaration(_project(tmp_path))
    assert decl.present is False and decl.wants == {}


def test_the_installed_set_is_readable_with_versions(tmp_path):
    root = _project(tmp_path)
    InstallRecord(modules={"web": "0.2.0", "wc": None}).save(root)
    got = read_install_record(root)
    assert got.modules == {"web": "0.2.0", "wc": None}
    assert got.as_lines() == ["wc (version unknown)", "web 0.2.0"], "sorted, so deterministic"
    assert read_install_record(tmp_path / "nowhere").as_lines() == ["no modules installed"]


# ── the announcement ──────────────────────────────────────────────────────────────────────


def _instructions(tmp_path: Path) -> Path:
    p = tmp_path / "CLAUDE.md"
    p.write_text("# Project\n\nhand-authored guidance\n", encoding="utf-8")
    return p


def test_the_announcement_is_written_into_its_own_section_and_nothing_outside_it_moves(tmp_path):
    p = _instructions(tmp_path)
    before = p.read_text(encoding="utf-8")
    result = announce_module(p, "workcycle", "The engine is installed.")
    assert result.wrote
    after = p.read_text(encoding="utf-8")
    begin, end = section_markers("workcycle")
    assert begin in after and end in after
    outside = after.split(begin)[0]
    assert outside.startswith(before), "every byte outside the section is unchanged"
    assert read_section(after, "workcycle").strip() == "The engine is installed."


def test_a_section_the_project_edited_is_left_alone_and_reported(tmp_path):
    p = _instructions(tmp_path)
    announce_module(p, "workcycle", "v1 text")
    p.write_text(p.read_text(encoding="utf-8").replace("v1 text", "v1 text, plus ours"),
                 encoding="utf-8")
    result = announce_module(p, "workcycle", "v2 text", last_written="v1 text")
    assert result.outcome == "left-alone"
    assert "plus ours" in p.read_text(encoding="utf-8"), "the project's edit is not restored"
    assert "v2 text" not in p.read_text(encoding="utf-8")


def test_with_no_instruction_file_the_installer_reports_and_creates_nothing(tmp_path):
    target = tmp_path / "CLAUDE.md"
    result = announce_module(target, "workcycle", "text")
    assert result.outcome == "no-instruction-file"
    assert not target.exists(), "the file is NOT created as a side effect of installing"


def test_withdrawing_removes_only_the_section(tmp_path):
    p = _instructions(tmp_path)
    before = p.read_text(encoding="utf-8")
    announce_module(p, "workcycle", "text")
    announce_module(p, "other", "another module's text")
    assert withdraw_announcement(p, "workcycle").wrote
    after = p.read_text(encoding="utf-8")
    assert before.strip() in after
    assert "another module's text" in after, "another module's section is untouched"
    assert read_section(after, "workcycle") is None


# ── the validation is IN FORCE, not merely available ──────────────────────────────────────
#
# An unwired validator is precisely the defect this group forbids: a guard that is declared
# and does not take effect. These two tests are the difference between a mechanism that
# exists and one that runs.

from set_orch.profile_deploy import (  # noqa: E402
    ManifestValidationError,
    _deploy_single_template,
)


def test_an_incomplete_declaration_stops_the_install_before_anything_is_written(tmp_path):
    template = tmp_path / "tmpl"
    template.mkdir()
    (template / "a.md").write_text("from the template\n", encoding="utf-8")
    (template / "manifest.yaml").write_text("core:\n  - a.md\n", encoding="utf-8")
    target = tmp_path / "proj"
    target.mkdir()

    with pytest.raises(ManifestValidationError) as exc:
        _deploy_single_template(template, target)

    assert {e.code for e in exc.value.errors} >= {E_NO_TREATMENT}
    assert not (target / "a.md").exists(), "refused BEFORE a byte was written"


def test_a_template_with_no_manifest_is_not_refused(tmp_path):
    """The legacy path deploys everything and declared nothing. Refusing it would break
    projects that never made a declaration — the requirement is about declarations that are
    incomplete, not about their absence."""
    template = tmp_path / "tmpl"
    template.mkdir()
    (template / "a.md").write_text("x\n", encoding="utf-8")
    target = tmp_path / "proj"
    target.mkdir()
    _deploy_single_template(template, target, dry_run=True)  # must not raise


def _announcing_template(tmp_path: Path, body: str = "The engine is installed.") -> Path:
    template = tmp_path / "tmpl"
    template.mkdir()
    (template / "a.md").write_text("from the template\n", encoding="utf-8")
    (template / "manifest.yaml").write_text(
        'version: "1.0"\n'
        "core:\n  - path: a.md\n    replace: true\n"
        f'announce:\n  file: CLAUDE.md\n  body: "{body}"\n',
        encoding="utf-8",
    )
    return template


def test_a_deploy_announces_the_module_and_records_what_it_wrote(tmp_path):
    template = _announcing_template(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    (target / "CLAUDE.md").write_text("# Project\n\nhand-authored\n", encoding="utf-8")

    messages = _deploy_single_template(template, target)
    assert any("Announced" in m for m in messages)
    assert "The engine is installed." in (target / "CLAUDE.md").read_text(encoding="utf-8")
    assert read_install_record(target).announcements["tmpl"] == "The engine is installed."


def test_a_deploy_into_a_project_with_no_instruction_file_reports_and_creates_nothing(tmp_path):
    template = _announcing_template(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()

    messages = _deploy_single_template(template, target)
    assert any("Not announced" in m for m in messages), messages
    assert not (target / "CLAUDE.md").exists()


def test_a_second_deploy_does_not_restore_a_section_the_project_edited(tmp_path):
    template = _announcing_template(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    (target / "CLAUDE.md").write_text("# Project\n", encoding="utf-8")
    _deploy_single_template(template, target)

    claude = target / "CLAUDE.md"
    claude.write_text(
        claude.read_text(encoding="utf-8").replace(
            "The engine is installed.", "The engine is installed. We also do X here."),
        encoding="utf-8",
    )
    messages = _deploy_single_template(template, target, force=True)
    assert any("Not announced" in m for m in messages), messages
    assert "We also do X here." in claude.read_text(encoding="utf-8")


def test_a_newer_generated_artifact_is_not_replaced_by_an_older_generator_s_output(tmp_path):
    """The guard is IN THE COPY PATH, not merely available as a function."""
    template = tmp_path / "tmpl"
    template.mkdir()
    (template / "skill.md").write_text('generatedBy: "1.1.1"\nold body\n', encoding="utf-8")
    (template / "manifest.yaml").write_text(
        'version: "1.0"\ncore:\n  - path: skill.md\n    replace: true\n', encoding="utf-8")
    target = tmp_path / "proj"
    target.mkdir()
    newer = target / "skill.md"
    newer.write_text('generatedBy: "1.9.0"\nnewer body\n', encoding="utf-8")

    messages = _deploy_single_template(template, target, force=True)
    assert any("newer generator at destination" in m for m in messages), messages
    assert "newer body" in newer.read_text(encoding="utf-8"), "the destination was left alone"
