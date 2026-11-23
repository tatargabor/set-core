"""project-role-rule (fleet-era-consolidation): the generated, machine-local role rule.

Every test builds real git repositories in tmp_path and injects the visibility decision,
so no test asks GitHub anything and the repository's own registry is never read."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from set_orch import project_roles as pr

REPO = Path(__file__).resolve().parents[2]


def repo(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.mkdir()
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    return p


def status(p: Path) -> str:
    return subprocess.run(["git", "-C", str(p), "status", "--porcelain"], capture_output=True, text=True).stdout


def vis_of(mapping: dict):
    return lambda path: mapping.get(Path(path).name, "unknown")


@pytest.fixture
def fleet(tmp_path):
    reg = {n: {"path": str(repo(tmp_path, n))} for n in ("pub", "pubdep", "privdep", "old")}
    reg["old"]["archived"] = True
    roles = {
        "pub": {"role": "The public tool.", "owns": ["cli"]},
        "pubdep": {"role": "A public consumer.", "depends_on": ["pub"]},
        "privdep": {"role": "A private consumer.", "depends_on": ["pub"]},
        "old": {"role": "The old tool.", "replaced_by": "pub"},
    }
    vis = vis_of({"pub": "public", "pubdep": "public", "privdep": "private", "old": "private"})
    return reg, roles, vis


def rule(reg, name) -> str:
    return (Path(reg[name]["path"]) / pr.RULE_REL).read_text()


def test_no_role_file_writes_nothing_and_exits_0(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("SET_CONFIG_DIR", str(tmp_path / "cfg"))
    assert pr.main([]) == 0
    out = capsys.readouterr().out
    assert out.startswith("no role file") and str(tmp_path / "cfg" / pr.ROLE_FILE_NAME) in out


def test_a_project_without_an_entry_gets_registry_facts_only(fleet):
    reg, roles, vis = fleet
    roles.pop("pubdep")
    pr.generate(reg, roles, vis=vis)
    text = rule(reg, "pubdep")
    assert "not described in the operator's role file" in text and "Visibility: public." in text


def test_a_hand_written_file_is_left_alone(fleet):
    reg, roles, vis = fleet
    target = Path(reg["pub"]["path"]) / pr.RULE_REL
    target.parent.mkdir(parents=True)
    target.write_text("my own notes\n")
    out = pr.generate(reg, roles, vis=vis)
    assert target.read_text() == "my own notes\n"
    assert any(n == "pub" and "without the generated-by marker" in why for n, why in out.skipped)


def test_regeneration_is_idempotent(fleet):
    reg, roles, vis = fleet
    pr.generate(reg, roles, vis=vis)
    before = {n: rule(reg, n) for n in reg}
    out = pr.generate(reg, roles, vis=vis)
    assert out.written == [] and sorted(out.unchanged) == sorted(reg)
    assert {n: rule(reg, n) for n in reg} == before


def test_the_rule_never_shows_in_git_status(fleet):
    reg, roles, vis = fleet
    assert all(status(Path(e["path"])) == "" for e in reg.values())
    pr.generate(reg, roles, vis=vis)
    for e in reg.values():
        assert (Path(e["path"]) / pr.RULE_REL).is_file()
        assert status(Path(e["path"])) == "", "the rule must be excluded, never shown as untracked"


def test_a_public_repo_names_public_relations_and_counts_private_ones(fleet):
    reg, roles, vis = fleet
    pr.generate(reg, roles, vis=vis)
    text = rule(reg, "pub")
    assert "`pubdep`" in text and "privdep" not in text and "1 private project" in text


def test_a_private_repo_names_everything(fleet):
    reg, roles, vis = fleet
    roles["privdep"]["depends_on"] = ["pub", "old"]
    pr.generate(reg, roles, vis=vis)
    assert "`old`" in rule(reg, "privdep") and "`pub`" in rule(reg, "privdep")


def test_an_undecidable_relation_is_not_named(fleet):
    reg, roles, vis = fleet
    vis2 = vis_of({"pub": "public", "pubdep": "unknown", "privdep": "private", "old": "private"})
    pr.generate(reg, roles, vis=vis2)
    text = rule(reg, "pub")
    assert "pubdep" not in text and "2 private projects" in text


def test_an_archived_project_opens_with_the_notice(fleet):
    reg, roles, vis = fleet
    pr.generate(reg, roles, vis=vis)
    head = rule(reg, "old").splitlines()[:4]
    assert any("ARCHIVED — do not develop this project" in line for line in head)
    assert "replaced by `pub`" in rule(reg, "old")


def test_unarchiving_removes_the_notice(fleet):
    reg, roles, vis = fleet
    pr.generate(reg, roles, vis=vis)
    reg["old"]["archived"] = False
    pr.generate(reg, roles, vis=vis)
    assert "ARCHIVED" not in rule(reg, "old")


def test_a_data_repository_gets_nothing(fleet):
    reg, roles, vis = fleet
    reg["pub"]["deploy"] = False
    pr.generate(reg, roles, vis=vis)
    assert not (Path(reg["pub"]["path"]) / pr.RULE_REL).exists()


def test_rule_state_for_the_doctor(fleet, tmp_path):
    reg, roles, vis = fleet
    cfg = tmp_path / "cfg"
    env = {"SET_CONFIG_DIR": str(cfg), "HOME": str(tmp_path)}
    path = reg["pub"]["path"]
    assert pr.rule_state(path, env)[0] == "skip"
    cfg.mkdir()
    (cfg / pr.ROLE_FILE_NAME).write_text("version: 1\nprojects: {}\n")
    assert pr.rule_state(path, env) == ("warn", f"{pr.RULE_REL} is missing")
    pr.generate(reg, roles, vis=vis)
    assert pr.rule_state(path, env)[0] == "ok"
    later = time.time() + 5
    os.utime(cfg / pr.ROLE_FILE_NAME, (later, later))
    assert pr.rule_state(path, env) == ("warn", f"{pr.RULE_REL} is older than the role file")


def test_end_to_end_set_project_roles(tmp_path):
    """The real command, a sandbox config dir: the role file and the registry are read from
    SET_CONFIG_DIR, and a public-visibility answer is never needed because both repos have no
    remote (unknown → the project is treated as public, the sibling as private)."""
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    a, b = repo(tmp_path, "alpha"), repo(tmp_path, "beta")
    (cfg / "projects.json").write_text(json.dumps({"projects": {"alpha": {"path": str(a)},
                                                                "beta": {"path": str(b)}}}))
    (cfg / pr.ROLE_FILE_NAME).write_text("version: 1\nprojects:\n  alpha: {role: A.}\n"
                                         "  beta: {role: B., depends_on: [alpha]}\n")
    env = {**os.environ, "SET_CONFIG_DIR": str(cfg), "SET_CORE_REGISTRY": "", "HOME": str(tmp_path)}
    r = subprocess.run([str(REPO / "bin" / "set-project"), "roles"], env=env, capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 0, r.stderr
    assert "2 written" in r.stdout
    text = (a / pr.RULE_REL).read_text()
    assert text.startswith(pr.MARKER) and "1 private project" in text and "beta" not in text
    assert status(a) == "" and status(b) == ""


def test_check_names_every_problem_and_passes_a_valid_file(tmp_path):
    reg = {"a": {}, "b": {}}
    good = tmp_path / "good.yaml"
    good.write_text("version: 1\nprojects:\n  a: {role: A., owns: [x], depends_on: [b]}\n  b: {replaced_by: a}\n")
    assert pr.validate(good, reg) == []
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 2\nprojects:\n  a: {rol: typo, depends_on: [a, zz], owns: x}\n  ghost: {role: G.}\n"
                   "  b: {replaced_by: [a]}\n")
    problems = "\n".join(pr.validate(bad, reg))
    for expected in ("version must be 1", "projects.a.rol: unknown key", "names the project itself",
                     "zz is not a registry name", "projects.a.owns: must be a list", "projects.ghost: not a registry name",
                     "projects.b.replaced_by"):
        assert expected in problems, expected


# -- flows: how to reach a neighbour (fleet-mandate-and-desk, project-role-rule) ----------


def test_a_rule_lists_its_flows_both_ways_and_the_command(fleet):
    reg, roles, vis = fleet
    roles["privdep"]["flows"] = [{"to": "pub", "what": "a new CLI flag", "how": "over the bus"},
                                 {"to": "old", "what": "the legacy export format"}]
    pr.generate(reg, roles, vis=vis)
    asker = rule(reg, "privdep")
    assert "## Reaching other projects" in asker
    assert "- a new CLI flag → ask `pub` (over the bus)" in asker
    assert "- the legacy export format → ask `old`" in asker   # no `how`, no empty brackets
    assert "()" not in asker
    assert 'set-fleet-ask <project> "<request>"' in asker
    # The side that is asked sees the same flow from the other end — when it may name the asker.
    asked = rule(reg, "old")
    assert "- the legacy export format ← comes from `privdep`" in asked


def test_a_public_repo_counts_a_flow_to_a_private_project_and_names_nothing_of_it(fleet):
    reg, roles, vis = fleet
    roles["pub"]["flows"] = [{"to": "privdep", "what": "SECRET-SUBJECT", "how": "SECRET-MANNER"},
                             {"to": "pubdep", "what": "release notes"}]
    roles["privdep"]["flows"] = [{"to": "pub", "what": "INCOMING-SECRET"}]
    pr.generate(reg, roles, vis=vis)
    text = rule(reg, "pub")
    assert "- release notes → ask `pubdep`" in text
    assert "1 flow to private projects, not named here" in text
    assert "1 flow from private projects, not named here" in text
    for leaked in ("privdep", "SECRET-SUBJECT", "SECRET-MANNER", "INCOMING-SECRET"):
        assert leaked not in text, leaked


def test_a_project_with_no_flows_still_gets_the_command(fleet):
    reg, roles, vis = fleet
    pr.generate(reg, roles, vis=vis)
    text = rule(reg, "pubdep")
    assert "## Reaching other projects" in text and "set-fleet-ask" in text
    assert "What this project asks others for" not in text
    assert "What others ask this project for" not in text


def test_a_project_nobody_described_still_gets_the_command(fleet):
    reg, roles, vis = fleet
    del roles["pubdep"]
    pr.generate(reg, roles, vis=vis)
    text = rule(reg, "pubdep")
    assert "not described in the operator's role file" in text and "set-fleet-ask" in text


def test_a_flow_to_an_unregistered_project_is_reported_and_left_out(fleet, tmp_path):
    reg, roles, vis = fleet
    roles["pubdep"]["flows"] = [{"to": "ghost", "what": "GHOST-SUBJECT"},
                                {"to": "pub", "what": "a real thing"}]
    pr.generate(reg, roles, vis=vis)
    text = rule(reg, "pubdep")
    assert "a real thing" in text
    assert "ghost" not in text and "GHOST-SUBJECT" not in text
    # Left OUT, not counted as a private neighbour: a typo is not a private project.
    assert "not named here" not in text
    # And in a private repo, where everything registered is named, it is still absent.
    roles["privdep"]["flows"] = [{"to": "ghost", "what": "GHOST-SUBJECT"}]
    pr.generate(reg, roles, vis=vis)
    private = rule(reg, "privdep")
    assert "ghost" not in private and "GHOST-SUBJECT" not in private

    role_file = tmp_path / "roles.yaml"
    role_file.write_text(
        "version: 1\nprojects:\n  pubdep:\n    flows:\n"
        "      - {to: ghost, what: something}\n"
        "      - {to: pubdep, what: to itself}\n"
        "      - {to: pub}\n"
        "      - {to: pub, what: fine, how: over the bus}\n"
        "      - {to: pub, what: fine, via: typo}\n"
        "      - just text\n")
    problems = "\n".join(pr.validate(role_file, reg))
    for expected in ("flows[0].to: ghost is not a registry name", "flows[1].to: names the project itself",
                     "flows[2].what: must be text", "flows[4].via: unknown key", "flows[5]: must be a mapping"):
        assert expected in problems, expected
    assert "flows[3]" not in problems

    good = tmp_path / "good.yaml"
    good.write_text("version: 1\nprojects:\n  pubdep:\n    flows:\n      - {to: pub, what: fine, how: over the bus}\n")
    assert pr.validate(good, reg) == []


def test_the_example_role_file_is_valid_and_shows_a_flow():
    import yaml

    example = REPO / "templates" / "project-roles.example.yaml"
    data = yaml.safe_load(example.read_text())
    registry = {name: {} for name in data["projects"]}
    assert pr.validate(example, registry) == []
    assert any(entry.get("flows") for entry in data["projects"].values())
