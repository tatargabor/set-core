"""Task 2.6 — what a project has wired in, and the states that are not two.

The three defects this file holds are all ones that already happened here: a
signal that is true of every project, a path built by stripping characters
instead of a prefix, and a capability reported connected on one shared file.
"""

from __future__ import annotations

import json

from set_orch.fleet import capabilities as cap


def _framework(tmp_path):
    """A miniature set-core: a core rules directory and one module manifest."""
    rules = tmp_path / "templates" / "core" / "rules"
    rules.mkdir(parents=True)
    for n in ("alpha.md", "beta.md"):
        (rules / n).write_text("x", encoding="utf-8")
    man = tmp_path / "modules" / "demo" / "set_project_demo" / "templates" / "demo-kit"
    man.mkdir(parents=True)
    (man / "manifest.yaml").write_text(
        "version: '1.0.0'\ncore:\n  - rules/gamma.md\n  - demo.config.ts\n", encoding="utf-8")
    return str(tmp_path)


def test_the_capability_set_is_data_not_a_hand_kept_list(tmp_path):
    """Adding a rule changes the report with nothing here edited — which is the
    property a hand-kept list cannot have, and it is why it is derived."""
    root = _framework(tmp_path)
    before = {c.name: len(c.targets) for c in cap.framework_capabilities(root)}
    (tmp_path / "templates" / "core" / "rules" / "delta.md").write_text("x", encoding="utf-8")
    after = {c.name: len(c.targets) for c in cap.framework_capabilities(root)}
    assert before["core-rules"] == 2 and after["core-rules"] == 3


def test_the_target_path_keeps_its_leading_dot(tmp_path):
    """The bug that made EVERY capability read not-connected, held so it cannot
    return: `.as_posix().lstrip("./")` strips a SET OF CHARACTERS, not a prefix,
    so `.claude/rules/x.md` came back as `claude/rules/x.md` — a path no project
    has. It was invisible in the code and obvious in the output."""
    caps = {c.name: c for c in cap.framework_capabilities(_framework(tmp_path))}
    assert all(t.startswith(".claude/rules/") for t in caps["core-rules"].targets)
    wrong = caps["core-rules"].targets[0].lstrip("./")
    assert wrong != caps["core-rules"].targets[0], "the wrong form must differ"


def _project(tmp_path, *rel, ledger=None, declaration=None):
    p = tmp_path / "proj"
    for r in rel:
        f = p / r
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")
    p.mkdir(parents=True, exist_ok=True)
    if ledger is not None:
        lp = p / "set" / ".deploy-manifest.json"
        lp.parent.mkdir(parents=True, exist_ok=True)
        lp.write_text(json.dumps({"files": {k: "sha" for k in ledger}}), encoding="utf-8")
    return str(p)


def test_a_capability_with_every_file_present_is_connected(tmp_path):
    caps = cap.framework_capabilities(_framework(tmp_path))
    proj = _project(tmp_path, ".claude/rules/alpha.md", ".claude/rules/beta.md")
    got = {c.name: c for c in cap.report_for_project(proj, capabilities=caps).capabilities}
    assert got["core-rules"].state == cap.CONNECTED


def test_one_shared_file_does_not_make_a_module_connected(tmp_path):
    """The false value found the first time this ran on real projects: two module
    capabilities reported CONNECTED on a single file they share with a third —
    "already wired in" about a project that is not."""
    caps = cap.framework_capabilities(_framework(tmp_path))
    proj = _project(tmp_path, ".claude/rules/gamma.md")     # 1 of demo-kit's 2
    got = {c.name: c for c in cap.report_for_project(proj, capabilities=caps).capabilities}
    assert got["demo-kit"].state == cap.PARTIAL
    assert got["demo-kit"].present == 1 and got["demo-kit"].total == 2


def test_absent_is_not_connected_rather_than_missing(tmp_path):
    """"Not wired in" invites wiring it in; dropping the row does not."""
    caps = cap.framework_capabilities(_framework(tmp_path))
    report = cap.report_for_project(_project(tmp_path), capabilities=caps)
    assert {c.name for c in report.capabilities} == {"core-rules", "demo-kit"}
    assert all(c.state == cap.NOT_CONNECTED for c in report.capabilities)


def test_an_unreadable_project_is_unknown_and_never_not_connected(tmp_path):
    """`not-connected` invites installing into a tree we cannot see. `unknown`
    does not, and one reason is given for the project rather than per capability."""
    caps = cap.framework_capabilities(_framework(tmp_path))
    report = cap.report_for_project(str(tmp_path / "nincs"), capabilities=caps)
    assert all(c.state == cap.UNKNOWN for c in report.capabilities)
    assert report.unreadable and report.as_dict()["not_connected"] == 0


def test_a_claude_directory_alone_proves_nothing(tmp_path):
    """Measured 12 of 12 before anything was built: every project somebody opens
    an agent in has `.claude/`. Counting it would have reported the framework
    installed everywhere."""
    caps = cap.framework_capabilities(_framework(tmp_path))
    proj = _project(tmp_path, ".claude/settings.json", ".claude/commands/opsx/apply.md")
    report = cap.report_for_project(proj, capabilities=caps)
    assert report.as_dict()["connected"] == 0 and report.as_dict()["partial"] == 0


def test_present_without_a_ledger_is_inferred_and_never_stale(tmp_path):
    """Un-ledgered is not a synonym for stale: for those files the framework
    cannot separate a project edit from its own drift, and `cannot tell` is the
    honest report. Measured: a ledger exists for 1 project in 12."""
    caps = cap.framework_capabilities(_framework(tmp_path))
    proj = _project(tmp_path, ".claude/rules/alpha.md", ".claude/rules/beta.md")
    got = {c.name: c for c in cap.report_for_project(proj, capabilities=caps).capabilities}
    assert got["core-rules"].inferred == 2 and got["core-rules"].ledgered == 0
    assert "cannot tell" in (got["core-rules"].reason or "")
    assert "stale" not in (got["core-rules"].reason or "")


def test_a_ledgered_file_is_reported_with_its_provenance(tmp_path):
    caps = cap.framework_capabilities(_framework(tmp_path))
    proj = _project(tmp_path, ".claude/rules/alpha.md", ".claude/rules/beta.md",
                    ledger=[".claude/rules/alpha.md"])
    report = cap.report_for_project(proj, capabilities=caps)
    got = {c.name: c for c in report.capabilities}
    assert report.ledger_present is True
    assert got["core-rules"].ledgered == 1 and got["core-rules"].inferred == 1


def test_no_declaration_is_reported_as_the_normal_case(tmp_path):
    """Task 2.9's assumption inverted: the declaration is the source WHERE IT
    EXISTS, and it exists for one project in twelve."""
    caps = cap.framework_capabilities(_framework(tmp_path))
    report = cap.report_for_project(_project(tmp_path), capabilities=caps)
    assert report.declared is False and report.versions == []


def test_nothing_about_the_project_reaches_THIS_modules_log(tmp_path, caplog):
    """Paths inside a consumer's tree are read here. The diagnostics name the
    capability and the count, never a path.

    ⚠ Scoped to this module's logger ON PURPOSE, and the reason is a finding
    rather than a convenience. The first version asserted over EVERY record and
    failed — on a line from `set_orch.module_install`, which logs the absolute
    project path when no declaration is found (`no project declaration at
    <path>/set/modules.yaml`). That is a pre-existing diagnostic in another
    capability, and widening this assertion to pass would have been the wrong
    repair in both directions: it would hide the finding AND stop guarding this
    module. Recorded in the task rather than fixed here, because it belongs to
    the module-install capability.
    """
    import logging
    caps = cap.framework_capabilities(_framework(tmp_path))
    proj = _project(tmp_path, ".claude/rules/alpha.md")
    with caplog.at_level(logging.DEBUG):
        cap.report_for_project(proj, capabilities=caps)
    mine = " ".join(r.getMessage() for r in caplog.records
                    if r.name.startswith("set_orch.fleet.capabilities"))
    assert mine, "the module logged nothing at all — this test would pass vacuously"
    assert proj not in mine and "alpha.md" not in mine


def test_the_neighbouring_module_still_logs_a_project_path(tmp_path, caplog):
    """The finding above, held as a test so it is not lost in prose.

    It fails the day `module_install` stops naming the path — which is the day
    this note should be deleted. A finding recorded only in a comment is one
    nobody re-checks.
    """
    import logging
    from set_orch.module_install import read_project_declaration
    proj = _project(tmp_path)
    with caplog.at_level(logging.DEBUG):
        read_project_declaration(proj)
    blob = " ".join(r.getMessage() for r in caplog.records)
    assert proj in blob, "module_install no longer logs the project path — delete this test"


# --------------------------------------------------------------------------- #
# the version half of task 2.9 — the answer inference is structurally blind to
#
# A file is either there or it is not, so a report built from file presence
# cannot express a HALF-UPGRADED project: every file is present, every capability
# reads connected, and the project is running a version it did not ask for. Only
# a declaration can say that, which is why the requirement puts it first.
#
# Measured 2026-08-19 across three real projects: **no declaration anywhere**, so
# this path is the exception here — and an exception nothing drives is a path
# that has never run.
# --------------------------------------------------------------------------- #

def _declared(tmp_path, wants: dict, installed: dict):
    """A project that asked for modules, and a record of what it actually has."""
    import json as _json
    (tmp_path / "set").mkdir(parents=True, exist_ok=True)
    lines = ["modules:"]
    for name, version in wants.items():
        lines.append(f"  {name}:" if version is None else f"  {name}:\n    version: \"{version}\"")
    (tmp_path / "set" / "modules.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "set" / ".installed-modules.json").write_text(
        _json.dumps({"modules": installed, "announcements": {}}), encoding="utf-8")
    return str(tmp_path)


def test_a_project_running_a_version_it_did_not_ask_for_is_reported_as_a_mismatch(tmp_path):
    """The case the whole declaration path exists for, driven end to end."""
    root = _declared(tmp_path, {"web": "1.2.0"}, {"web": "1.1.0"})
    report = cap.report_for_project(root, capabilities=[])
    assert report.declared is True
    assert report.versions == [
        {"module": "web", "expected": "1.2.0", "installed": "1.1.0", "state": "mismatch"}
    ]


def test_a_version_that_agrees_is_a_match_so_the_mismatch_above_means_something(tmp_path):
    """The other direction. A report that says `mismatch` for everything is not a
    report, and a positive-only test cannot tell the two apart."""
    root = _declared(tmp_path, {"web": "1.2.0"}, {"web": "1.2.0"})
    states = {v["module"]: v["state"] for v in cap.report_for_project(root, capabilities=[]).versions}
    assert states == {"web": "match"}


def test_a_module_asked_for_but_not_installed_is_unknown_never_a_match(tmp_path):
    """`unknown` is not a polite way of saying fine.

    A module the project wants and does not have compares as unknown, and so does
    one whose version cannot be read on either side. Rendering either as a match
    removes exactly the answer the comparison was asked for — the false-value
    class, in the reassuring direction.
    """
    root = _declared(tmp_path, {"web": "1.2.0", "mobile": None}, {})
    states = {v["module"]: v["state"] for v in cap.report_for_project(root, capabilities=[]).versions}
    assert states == {"web": "unknown", "mobile": "unknown"}


def test_a_project_that_declared_nothing_reports_no_versions_rather_than_agreement(tmp_path):
    """`declared: False` and an empty comparison list, because a project that
    never adopted the mechanism has not agreed with anything — and a surface that
    renders "no mismatches" over it is reporting calm it did not verify."""
    report = cap.report_for_project(str(tmp_path), capabilities=[])
    assert report.declared is False
    assert report.versions == []
