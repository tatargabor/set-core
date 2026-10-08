"""The three verification commands end to end, ON THE FIXTURE CORPUS (5.4).

`doctor`, `findability` and `eval` run through the real CLI over a temp copy
of `tests/fixtures/kb/corpus` — the synthetic corpus the oracle uses — so the
output measured here is the output a project sees, not a library call."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from conftest_kb import git, write
from test_kb_cli import run_cli

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "kb"


def fixture_project(tmp_path) -> Path:
    root = tmp_path / "fixtureproj"
    root.mkdir()
    shutil.copytree(FIXTURE / "corpus", root / "corpus")
    shutil.copy2(FIXTURE / "kb.config.json", root / "kb.config.json")  # the legacy location, as W2 loads it
    git(root, "init", "-q")
    write(root / ".gitignore", ".set/\n")
    return root


def test_doctor_on_the_fixture_corpus(tmp_path):
    root = fixture_project(tmp_path)
    run_cli(["search", "pricing"], cwd=root)  # build the index
    r = run_cli(["doctor", "--json"], cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.loads(r.stdout)
    by_root = {row["root"]: row for row in d["roots"]}
    assert by_root["corpus/planning"]["files"] == 8, "the fixture's planning root, counted"
    rules = {e["rule"]: e["files"] for e in d["exclusions"]}
    assert rules.get("**/sessions/**") == 1, "the agent-session dump shows under its rule"
    assert rules.get("dist/") == 1 and rules.get(".venv*/") == 1, "build output and the virtualenv are counted"


def test_findability_on_the_fixture_corpus(tmp_path):
    root = fixture_project(tmp_path)
    r = run_cli(["findability", "--json"], cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.loads(r.stdout)
    paths = {c["path"]: c for c in d["candidates"]}
    assert "corpus/meetings/2026-09-12-tervezes-part1.md" in paths, "the recording's readable form is discovered"
    assert paths["corpus/meetings/2026-09-12-tervezes-part1.md"]["recording"] == "2026-09-12-tervezes-part1.jsonl"
    assert d["level1"]["missed"] == 0
    assert d["level2"]["rate"] == 1.0, "the title query returns the transcript in the top 10"


def test_eval_on_the_fixture_corpus(tmp_path):
    root = fixture_project(tmp_path)
    write(
        root / "set" / "knowledge" / "kb-golden.json",
        json.dumps(
            {
                "queries": [
                    {"id": "budget", "q": "budget planning", "targets": ["corpus/planning/overview.md"]},
                    {"id": "recording", "q": "őszi sprint tervező megbeszélés", "targets": ["corpus/meetings/2026-09-12-tervezes-part1.md"]},
                    {"id": "accented", "q": "szamlazas dijbekero", "targets": ["corpus/planning/költségvetés-jegyzet.md"]},
                ],
                "control": {"q": "pricing", "targets": ["corpus/clients/client-alfa/alfa-emails.md"]},
            },
            ensure_ascii=False,
        ),
    )
    r = run_cli(["eval", "--json"], cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.loads(r.stdout)
    assert d["metrics"]["recallAtK"] == 1.0 and d["metrics"]["mrr"] == 1.0
    assert d["control"]["q"] == "pricing" and d["control"]["recallAtK"] == 1.0
    # The same run with the lane off — the two arms of a measurement.
    r2 = run_cli(["eval", "--no-lane", "--json"], cwd=root)
    d2 = json.loads(r2.stdout)
    assert d2["lane"] is False and d2["metrics"]["recallAtK"] == 1.0
