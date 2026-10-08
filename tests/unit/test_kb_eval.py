"""`set-kb eval`: the golden-set contract — shape rejection, multi-target
scoring, the control arm printed verbatim, the fail-closed denominator, and
the lane flag that takes the reserved lane out of every query in a run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest_kb import make_repo, write
from set_kb.eval import DEFAULT_GOLDEN_REL, EvalError, load_golden, run_eval
from set_kb.lifecycle import load_project

BODY = "\n\n" + "word " * 30 + "\n"


def golden_file(root, pairs, control=None):
    payload = {"queries": pairs} if control is not None else pairs
    if control is not None:
        payload["control"] = control
    return write(Path(root) / DEFAULT_GOLDEN_REL, json.dumps(payload, ensure_ascii=False))


def eval_project(tmp_path):
    root = make_repo(tmp_path, "evalproj")
    write(root / "docs" / "budget.md", "# Budget planning\n\nthe budget process and the invoice cycle" + BODY)
    write(root / "docs" / "handbook.md", "# Delivery handbook\n\nhow delivery and releases work" + BODY)
    write(root / "clients" / "mail.md", "# Client mail\n\nthe pricing question from the client" + BODY)
    return load_project(root)


PAIRS = [
    {"id": "budget", "q": "budget planning", "targets": ["docs/budget.md"]},
    {"id": "delivery", "q": "delivery releases", "targets": ["docs/handbook.md", "docs/nowhere.md"]},
    {"id": "pricing", "q": "pricing question", "targets": ["clients/mail.md"]},
]


def test_golden_shape_rejects_a_wrong_fixture(tmp_path):
    """A fixture in another shape is an error naming the entry, never a
    partial run over the parseable prefix."""
    root = make_repo(tmp_path, "shape")
    write(root / DEFAULT_GOLDEN_REL, json.dumps([{"id": "a", "q": "x"}]))  # no targets
    with pytest.raises(EvalError) as e:
        load_golden(str(root / DEFAULT_GOLDEN_REL))
    assert "golden[0]" in str(e.value) and "targets" in str(e.value)
    write(root / DEFAULT_GOLDEN_REL, json.dumps({"nonsense": True}))
    with pytest.raises(EvalError):
        load_golden(str(root / DEFAULT_GOLDEN_REL))
    write(root / DEFAULT_GOLDEN_REL, "{not json")
    with pytest.raises(EvalError):
        load_golden(str(root / DEFAULT_GOLDEN_REL))


def test_eval_reports_recall_mrr_and_multi_targets(tmp_path):
    project = eval_project(tmp_path)
    golden_file(project.root, PAIRS)
    pairs, control = load_golden(str(golden_file(project.root, PAIRS)))
    report = run_eval(project, pairs, k=5, control=control)
    m = report.metrics()
    # Per-pair recall: budget 1.0, delivery 0.5 (its second target does not
    # exist), pricing 1.0 — the mean is 5/6.
    assert abs(m["recallAtK"] - 0.8333) < 0.001, "recall is the mean per-pair target fraction"
    assert m["rank1"] > 0
    # multi-target: "delivery releases" names two targets, one of which does
    # not exist — recall for that pair is 0.5 and the run does not crash.
    delivery = next(r for r in report.results if r.id == "delivery")
    assert delivery.found == 1 and delivery.first_rank is not None


def test_failed_search_keeps_the_denominator(tmp_path, monkeypatch):
    """AC: WHEN one golden query raises THEN the denominator stays and the
    failure is listed."""
    project = eval_project(tmp_path)
    golden_file(project.root, PAIRS)
    pairs, _control = load_golden(str(Path(project.root) / DEFAULT_GOLDEN_REL))

    from set_kb import eval as eval_mod

    real = eval_mod.search_page

    def boom(store, query, opts):
        if "pricing" in query:
            raise RuntimeError("simulated engine failure")
        return real(store, query, opts)

    monkeypatch.setattr(eval_mod, "search_page", boom)
    report = run_eval(project, pairs, k=5)
    assert len(report.results) == 3, "the denominator is the full pair count"
    assert len(report.failures) == 1
    assert "simulated engine failure" in report.failures[0].error
    m = report.metrics()
    assert m["recallAtK"] < 1.0, "the failed pair scores as a miss, not as absence-of-evidence"
    failed = [r for r in report.results if r.id == "pricing"][0]
    assert failed.first_rank is None and failed.error


def test_control_arm_prints_the_query_and_its_recall(tmp_path):
    """AC: WHEN the control arm runs THEN the report shows the control query
    verbatim with its recall next to the real arm's."""
    project = eval_project(tmp_path)
    pairs, control = load_golden(
        str(golden_file(project.root, PAIRS, control={"q": "budget planning", "targets": ["docs/budget.md"]}))
    )
    report = run_eval(project, pairs, k=5, control=control)
    assert report.control_q == "budget planning"
    assert report.control_found == 1 and report.control_targets == 1
    d = report.to_json_dict(str(project.root))
    assert d["control"]["q"] == "budget planning" and d["control"]["recallAtK"] == 1.0


def test_lane_disabled_ignores_the_lane_for_every_query(tmp_path):
    """AC: WHEN eval disables the lane THEN ranking uses no reserved lane for
    any query in the run — the arm flag decides, not the config quota."""
    root = make_repo(tmp_path, "lane")
    # Three short planning docs that outrank the client mail on raw BM25 (the
    # mail buries its query words under filler, so length normalisation and
    # the short docs beat it).
    for name in ("a", "b", "c"):
        write(root / f"{name}.md", f"# Zephyr topic {name}\n\nzephyr topic\n" + BODY)
    write(root / "clients" / "mail.md", "# Client mail\n\n" + "filler " * 200 + " zephyr topic\n")
    write(
        Path(root) / "set" / "knowledge" / "kb.json",
        json.dumps({"channels": [{"channel": "client", "roots": [""], "include": ["clients/**"]}], "ranking": {"laneChannels": ["client"], "laneQuota": 1.0}}),
    )
    from set_kb.config import load_config

    project = load_project(root)
    project.config = load_config(project.root)
    pairs = [{"id": "lanecheck", "q": "zephyr topic", "targets": ["clients/mail.md"]}]
    on = run_eval(project, pairs, k=5, lane=True)
    off = run_eval(project, pairs, k=5, lane=False)
    assert on.lane is True and off.lane is False
    on_pair = on.results[0]
    off_pair = off.results[0]
    assert on_pair.first_rank == 1, "a 100% lane quota reserves slot 1 for the client hit"
    assert off_pair.first_rank != 1, "with the lane off, pure BM25 puts the short planning docs first"


def test_run_eval_without_an_index_and_with_no_reindex(tmp_path):
    project = eval_project(tmp_path)
    pairs, _ = load_golden(str(golden_file(project.root, PAIRS)))
    with pytest.raises(EvalError):
        run_eval(project, pairs, no_reindex=True), "no index exists yet"
    run_eval(project, pairs)  # builds the index
    again = run_eval(project, pairs, no_reindex=True)
    assert len(again.results) == 3
