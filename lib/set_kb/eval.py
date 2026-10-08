"""Retrieval eval over a project-owned golden set, with a control arm.

The contract is the originating evaluator's (design D12): `{id, q, targets[]}`
pairs, multi-target scoring, a control query printed verbatim next to the real
arm, and a FAILED SEARCH COUNTS AS A MISS — the denominator never shrinks, so
a run where half the queries crash cannot look like a run where half the
queries missed. The golden set lives in the project
(`set/knowledge/kb-golden.json` by default) and never in set-core: it is
derived from the project's own corpus questions.

This is also the measuring half of the re-measurement gate (requirement:
moving-a-project-onto-the-shared-engine-is-gated-by-a-re-measurement): the
arm (lane on/off) is a flag, so both arms run through exactly this code.

Rank numbers are 1-based positions among the returned hits; a target matches
when the hit's repository-relative path equals it (NFC, `./` stripped — the
same normalisation everywhere else).
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from set_kb.config import KbConfig
from set_kb.search import search_page

logger = logging.getLogger(__name__)

DEFAULT_GOLDEN_REL = os.path.join("set", "knowledge", "kb-golden.json")


class EvalError(ValueError):
    """The golden set is not in the contract shape — rejected, never guessed
    around (requirement: a fixture in another shape is an error)."""


@dataclass
class PairResult:
    id: str
    q: str
    targets: list
    found: int = 0  # targets present in the top k
    first_rank: "int | None" = None  # best rank among targets; None = none in top k
    error: "str | None" = None


@dataclass
class EvalReport:
    golden: str
    k: int
    lane: bool
    results: list = field(default_factory=list)
    control_q: "str | None" = None
    control_found: "int | None" = None
    control_targets: "int | None" = None
    control_note: "str | None" = None
    notes: list = field(default_factory=list)

    @property
    def failures(self) -> list:
        return [r for r in self.results if r.error]

    @property
    def misses(self) -> list:
        return [r for r in self.results if not r.error and r.first_rank is None]

    def metrics(self) -> dict:
        n = len(self.results) or 1
        recall = sum((r.found / len(r.targets)) if r.targets else 0.0 for r in self.results) / n
        mrr = sum((1.0 / r.first_rank) if r.first_rank else 0.0 for r in self.results) / n

        def frac(pred) -> float:
            return sum(1 for r in self.results if not r.error and r.first_rank is not None and pred(r.first_rank)) / n

        return {
            "recallAtK": round(recall, 4),
            "mrr": round(mrr, 4),
            "rank1": round(frac(lambda rk: rk == 1), 4),
            "top3": round(frac(lambda rk: rk <= 3), 4),
            "top5": round(frac(lambda rk: rk <= 5), 4),
        }

    def to_json_dict(self, root: str) -> dict:
        return {
            "version": 1,
            "command": "eval",
            "root": root,
            "golden": self.golden,
            "k": self.k,
            "lane": self.lane,
            "pairs": len(self.results),
            "metrics": self.metrics(),
            # Fail-closed: a failed search is a MISS, and the failure is listed
            # — the denominator stays the full pair count.
            "failures": [{"id": r.id, "error": r.error} for r in self.failures],
            "misses": [
                {"id": r.id, "q": r.q, "targets": r.targets, "foundTargets": r.found}
                for r in self.misses
            ],
            "control": (
                {
                    "q": self.control_q,
                    "targets": self.control_targets,
                    "found": self.control_found,
                    "recallAtK": round(self.control_found / self.control_targets, 4)
                    if self.control_found is not None and self.control_targets
                    else None,
                    "note": self.control_note,
                }
                if self.control_q is not None
                else None
            ),
            "notes": list(self.notes),
        }


# ── the golden set ───────────────────────────────────────────────────────────


def _check_pair(entry, where: str) -> None:
    if not isinstance(entry, dict):
        raise EvalError(f"{where}: expected an object with id, q, targets")
    if not isinstance(entry.get("id"), str) or not entry["id"].strip():
        raise EvalError(f"{where}.id: expected a non-empty string")
    if not isinstance(entry.get("q"), str) or not entry["q"].strip():
        raise EvalError(f"{where} ({entry.get('id', '?')}).q: expected a non-empty query string")
    targets = entry.get("targets")
    if not isinstance(targets, list) or not targets or not all(isinstance(t, str) and t.strip() for t in targets):
        raise EvalError(f"{where} ({entry['id']}).targets: expected a non-empty list of repository-relative paths")


def load_golden(path) -> "tuple[list, dict | None]":
    """(pairs, control) from a golden-set file. Two accepted shapes: a bare
    list of pairs, or an object `{"queries": [...], "control": {q, targets}}`.
    Anything else — including a pair missing a field — is an EvalError naming
    the entry, never a partial run over the parseable prefix."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as e:
        raise EvalError(f"golden set {path}: not valid JSON: {e}") from e
    pairs = data
    control = None
    if isinstance(data, dict):
        pairs = data.get("queries")
        control = data.get("control")
        if control is not None:
            if not isinstance(control, dict) or not isinstance(control.get("q"), str) or not control["q"].strip():
                raise EvalError("control: expected an object with a q and (optionally) targets")
    if not isinstance(pairs, list) or not pairs:
        raise EvalError(f"golden set {path}: expected a list of {{id, q, targets}} pairs (or an object with \"queries\")")
    for i, entry in enumerate(pairs):
        _check_pair(entry, f"golden[{i}]")
    return pairs, control


# ── the run ──────────────────────────────────────────────────────────────────


def _norm_target(t: str) -> str:
    p = t.strip()
    p = p[2:] if p.startswith("./") else p
    return unicodedata.normalize("NFC", p.replace(os.sep, "/"))


def score_query(store, query: str, targets: list, opts) -> PairResult:
    """One query through the index — a raised search is a MISS with the error
    recorded, never an aborted run and never a shrunk denominator."""
    want = {_norm_target(t) for t in targets}
    result = PairResult(id="", q=query, targets=sorted(want))
    try:
        page = search_page(store, query, opts)
    except Exception as e:  # noqa: BLE001 — the failure IS the measurement
        logger.warning("kb eval: search failed for %r: %s", query, e)
        result.error = f"{type(e).__name__}: {e}"
        return result
    for rank, h in enumerate(page.hits, 1):
        rel = f"{h.root}/{h.path}" if h.root else h.path
        if rel in want:
            result.found += 1
            if result.first_rank is None:
                result.first_rank = rank
    return result


def run_eval(project, pairs: list, k: int = 10, lane: bool = True, control: "dict | None" = None, no_reindex: bool = False) -> EvalReport:
    """Refresh once, then every query runs `--no-reindex` against that index:
    an eval is a measurement run (design D6), and fifty incremental refresh
    walks would measure the filesystem, not the retrieval."""
    from set_kb.config import search_options
    from set_kb.lifecycle import refresh
    from set_kb.store import SqliteFtsStore

    rr = refresh(project, no_reindex=no_reindex)
    report = EvalReport(golden="", k=k, lane=lane, notes=list(rr.notes))

    if not os.path.exists(project.db_path):
        raise EvalError(
            f"no index exists at {project.db_path} — run a search or `set-kb index` first (--no-reindex needs an index)"
        )
    store = SqliteFtsStore(project.db_path)
    store.init()

    lane_channels = project.config.ranking.get("laneChannels", [])
    overrides: dict = {"limit": k}
    if not lane or not lane_channels:
        # AC: lane disabled for measurement — no query in the run may use it.
        # (A project with no lane configured never had one to disable.)
        overrides["lane_quota"] = 0
        overrides["lane_channels"] = ()
    opts = search_options(project.config, **overrides)

    try:
        for p in pairs:
            r = score_query(store, p["q"], p["targets"], opts)
            r.id = p["id"]
            report.results.append(r)
        if control is not None:
            c_targets = control.get("targets") or []
            c = score_query(store, control["q"], c_targets, opts)
            report.control_q = control["q"]
            report.control_targets = len(c.targets)
            report.control_found = c.found
            if not c_targets:
                report.control_note = "the control query ran, but no targets are configured for it — add \"targets\" to measure recall"
            elif c.error:
                report.control_note = f"the control search failed: {c.error}"
    finally:
        store.close()
    return report


def golden_path_for(project_root, override: "str | None" = None) -> str:
    """The golden-set location: the --golden override, else the project's
    `set/knowledge/kb-golden.json`."""
    return override or str(Path(project_root) / DEFAULT_GOLDEN_REL)


__all__ = ["DEFAULT_GOLDEN_REL", "EvalError", "EvalReport", "PairResult", "golden_path_for", "load_golden", "run_eval"]
