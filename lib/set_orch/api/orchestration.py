"""Orchestration state, changes, plans, digest, coverage, requirements, settings, memory routes."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Query

from ..state import load_state, StateCorruptionError
from .helpers import (
    _resolve_project,
    _state_path,
    _log_path,
    _sentinel_dir,
    _load_archived_changes,
    _list_worktrees,
    _enrich_changes,
    _claude_mangle,
    _PURPOSE_LABELS,
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/{project}/state")
def get_state(project: str, lineage: Optional[str] = None):
    """Get full orchestration state for a project.

    Section 13.4: when `?lineage=` is provided, the merged change list is
    filtered to that lineage (special value `__all__` returns the union).
    The top-level state fields (status, plan_version, etc.) are always
    returned as-is — they describe the LIVE sentinel, not a historical
    lineage.
    """
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
        data = state.to_dict()
        _enrich_changes(data, project_path)
        # Merge archived changes from previous replan cycles
        archived = _load_archived_changes(project_path)
        if archived:
            current_names = {c["name"] for c in data.get("changes", [])}
            for ac in archived:
                if ac["name"] not in current_names:
                    data["changes"].append(ac)
        # Section 13.4 — apply the lineage filter to the merged change list.
        from .lineages import apply_lineage_filter, resolve_lineage_default
        effective_lineage = lineage or resolve_lineage_default(project_path)
        if effective_lineage and effective_lineage != "__all__":
            data["changes"] = apply_lineage_filter(
                data.get("changes", []), effective_lineage,
            )
        data["effective_lineage"] = effective_lineage
        return data
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")


@router.get("/api/{project}/changes")
def list_changes(project: str, status: Optional[str] = Query(None)):
    """List orchestration changes, optionally filtered by status."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    changes = state.changes
    if status:
        changes = [c for c in changes if c.status == status]

    result = []
    for c in changes:
        d = c.to_dict()
        if c.worktree_path:
            wt_path = Path(c.worktree_path)
            # Enrich with loop-state
            loop_file = wt_path / ".set" / "loop-state.json"
            if loop_file.exists():
                try:
                    with open(loop_file) as f:
                        ls = json.load(f)
                    d["iteration"] = ls.get("current_iteration", 0)
                    d["max_iterations"] = ls.get("max_iterations", 0)
                except (json.JSONDecodeError, OSError):
                    pass
            # Enrich with available log files
            logs_dir = wt_path / ".claude" / "logs"
            if logs_dir.is_dir():
                d["logs"] = sorted(
                    f.name for f in logs_dir.iterdir()
                    if f.is_file() and f.suffix == ".log"
                )
        result.append(d)
    return result


@router.get("/api/{project}/changes/{name}")
def get_change(project: str, name: str):
    """Get a single change by name."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    for c in state.changes:
        if c.name == name:
            d = c.to_dict()
            # Enrich with loop-state
            if c.worktree_path:
                loop_file = Path(c.worktree_path) / ".set" / "loop-state.json"
                if loop_file.exists():
                    try:
                        with open(loop_file) as f:
                            ls = json.load(f)
                        d["iteration"] = ls.get("current_iteration", 0)
                        d["max_iterations"] = ls.get("max_iterations", 0)
                    except (json.JSONDecodeError, OSError):
                        pass
            return d
    raise HTTPException(404, f"Change not found: {name}")


def _load_journal_entries(journal_path: Path) -> list[dict]:
    if not journal_path.exists():
        return []
    entries: list[dict] = []
    try:
        with open(journal_path) as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entries.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        logger.warning("Failed to read journal %s: %s", journal_path, exc)
        return []
    return entries


_GATES = ("build", "test", "e2e", "review", "smoke", "scope_check", "rules", "e2e_coverage")


def _parse_journal_ts(ts) -> float:
    """Parse a journal entry timestamp to epoch seconds, 0.0 on any failure.

    Must return a float unconditionally — callers use the result in
    arithmetic (sort keys, abs-delta comparisons). A separate helper from
    `_parse_ts` (defined later in the file) avoids shadow issues: the
    other `_parse_ts` returns `float | None` which would crash the
    grouping logic with `TypeError: unsupported operand type(s) for -`.
    """
    if ts is None:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def _group_journal_by_gate(entries: list[dict]) -> dict[str, list[dict]]:
    """Pair result/output/ms entries into per-run records grouped by gate.

    Strategy: iterate chronologically and for each `<gate>_result` entry,
    attach the most-recent `<gate>_output` and `gate_<gate>_ms` that share
    a timestamp within a ±2s window. Each result closes one run.
    """
    grouped: dict[str, list[dict]] = {g: [] for g in _GATES}
    run_counters: dict[str, int] = {g: 0 for g in _GATES}

    by_gate_field: dict[tuple[str, str], list[dict]] = {}
    for e in entries:
        field = e.get("field", "")
        for g in _GATES:
            if field == f"{g}_result":
                by_gate_field.setdefault((g, "result"), []).append(e)
            elif field == f"{g}_output":
                by_gate_field.setdefault((g, "output"), []).append(e)
            elif field == f"gate_{g}_ms":
                by_gate_field.setdefault((g, "ms"), []).append(e)

    def _pick_closest(entries: list[dict], target_ts: float) -> dict | None:
        """Return the entry within ±2s of target_ts with the minimum delta."""
        best: dict | None = None
        best_delta = 2.0
        for e in entries:
            delta = abs(_parse_journal_ts(e.get("ts", "")) - target_ts)
            if delta <= best_delta:
                best = e
                best_delta = delta
        return best

    for gate in _GATES:
        results = by_gate_field.get((gate, "result"), [])
        outputs = by_gate_field.get((gate, "output"), [])
        timings = by_gate_field.get((gate, "ms"), [])
        for r in results:
            run_counters[gate] += 1
            r_ts = _parse_journal_ts(r.get("ts", ""))
            output_entry = _pick_closest(outputs, r_ts)
            ms_entry = _pick_closest(timings, r_ts)
            grouped[gate].append(
                {
                    "run": run_counters[gate],
                    "result": r.get("new"),
                    "output": output_entry.get("new") if output_entry else None,
                    "ms": ms_entry.get("new") if ms_entry else None,
                    "ts": r.get("ts"),
                }
            )

    return {g: runs for g, runs in grouped.items() if runs}


@router.get("/api/{project}/changes/{name}/journal")
def get_change_journal(project: str, name: str):
    """Return raw journal entries plus per-gate grouped run history."""
    project_path = _resolve_project(project)
    sp = _state_path(project_path)
    if not sp.exists():
        raise HTTPException(404, "No orchestration state found")
    try:
        state = load_state(str(sp))
    except StateCorruptionError as e:
        raise HTTPException(500, f"Corrupt state: {e.detail}")

    if not any(c.name == name for c in state.changes):
        raise HTTPException(404, f"Change not found: {name}")

    journal_path = Path(os.path.dirname(str(sp))) / "journals" / f"{name}.jsonl"
    entries = _load_journal_entries(journal_path)
    # Sort by (ts, seq) — `ts` is the primary key so daemon-restart seq
    # collisions don't reorder older entries after newer ones. `seq` is
    # the tiebreaker for entries written within the same millisecond.
    entries.sort(key=lambda e: (_parse_journal_ts(e.get("ts", "")), e.get("seq", 0)))
    grouped = _group_journal_by_gate(entries)
    return {"entries": entries, "grouped": grouped}


@router.get("/api/{project}/worktrees")
def list_worktrees_endpoint(project: str):
    """List git worktrees with loop-state and activity data."""
    project_path = _resolve_project(project)
    return _list_worktrees(project_path)
@router.get("/api/{project}/plans")
def list_plans(project: str):
    """List decompose plan files."""
    project_path = _resolve_project(project)
    plans_dir = project_path / "set" / "orchestration" / "plans"
    if not plans_dir.is_dir():
        return {"plans": []}
    plans = []
    for f in sorted(plans_dir.iterdir()):
        if f.is_file() and f.suffix == ".json":
            plans.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).astimezone().isoformat(),
            })
    return {"plans": plans}


@router.get("/api/{project}/plans/{filename}")
def get_plan(project: str, filename: str):
    """Read a decompose plan JSON file."""
    if ".." in filename or "/" in filename or not filename.endswith(".json"):
        raise HTTPException(400, "Invalid filename")
    project_path = _resolve_project(project)
    plan_file = project_path / "set" / "orchestration" / "plans" / filename
    if not plan_file.exists():
        raise HTTPException(404, f"Plan not found: {filename}")
    try:
        with open(plan_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(500, f"Failed to read plan: {e}")


@router.get("/api/{project}/digest")
def get_digest(project: str, lineage: Optional[str] = None):
    """Return digest data: index, requirements, coverage, domains, dependencies, ambiguities.

    Section 13.4 / 4b.4: when `?lineage=` is provided, the endpoint
    routes to the lineage-specific digest directory (`digest-<slug>/`).
    When the lineage has no saved digest, returns
    `{"exists": false, "lineage_unavailable": true}` per AC-27c.

    Section 11.3: REQ attribution falls back to `spec-coverage-history.jsonl`
    when a REQ isn't covered by any live-plan change but a historic
    change merged it.  Such entries are flagged with
    `merged_by_archived = true`.
    """
    from .lineages import resolve_lineage_default
    project_path = _resolve_project(project)
    effective_lineage = lineage or resolve_lineage_default(project_path)

    # Resolve the digest dir for the requested lineage.
    digest_dir = project_path / "set" / "orchestration" / "digest"
    if effective_lineage and effective_lineage not in ("__all__", "__legacy__"):
        from ..types import slug as _slug
        slugged = project_path / "set" / "orchestration" / f"digest-{_slug(effective_lineage)}"
        if slugged.is_dir():
            digest_dir = slugged
        elif not digest_dir.is_dir():
            # Neither lineage-specific nor live exists.
            return {
                "exists": False,
                "lineage_unavailable": True,
                "effective_lineage": effective_lineage,
            }
    if not digest_dir.is_dir():
        return {"exists": False, "effective_lineage": effective_lineage}

    result: dict = {"exists": True}

    # Read JSON files
    for name in ("index", "requirements", "coverage", "dependencies", "ambiguities", "conventions", "coverage-merged"):
        fpath = digest_dir / f"{name}.json"
        if fpath.exists():
            try:
                with open(fpath) as f:
                    result[name.replace("-", "_")] = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

    # Read domain summaries
    domains_dir = digest_dir / "domains"
    if domains_dir.is_dir():
        domains = {}
        for df in sorted(domains_dir.iterdir()):
            if df.is_file() and df.suffix == ".md":
                try:
                    domains[df.stem] = df.read_text()
                except OSError:
                    pass
        result["domains"] = domains

    # Read triage.md
    triage = digest_dir / "triage.md"
    if triage.exists():
        try:
            result["triage"] = triage.read_text()
        except OSError:
            pass

    # Read data-definitions.md
    datadef = digest_dir / "data-definitions.md"
    if datadef.exists():
        try:
            result["data_definitions"] = datadef.read_text()
        except OSError:
            pass

    # Enrich requirements with parsed BDD scenarios from spec source files
    _enrich_requirements_with_scenarios(result, project_path)

    # Attach test coverage from orchestration state if available
    # Coverage can be at state.extras.test_coverage (legacy) or per-change extras
    state_file = project_path / "orchestration-state.json"
    if state_file.exists():
        try:
            with open(state_file) as f:
                state_data = json.load(f)

            # Try state-level first (legacy)
            tc = state_data.get("extras", {}).get("test_coverage")
            if not tc:
                tc = state_data.get("test_coverage")

            # Aggregate from per-change coverage if no state-level data
            if not tc:
                all_cases = []
                covered = set()
                uncovered = set()
                non_testable = set()
                passed = 0
                failed = 0
                for ch in state_data.get("changes", []):
                    # extras are flattened to top-level in JSON serialization
                    ch_tc = ch.get("test_coverage") or ch.get("extras", {}).get("test_coverage")
                    if ch_tc:
                        all_cases.extend(ch_tc.get("test_cases", []))
                        covered.update(ch_tc.get("covered_reqs", []))
                        uncovered.update(ch_tc.get("uncovered_reqs", []))
                        non_testable.update(ch_tc.get("non_testable_reqs", []))
                        passed += ch_tc.get("passed", 0)
                        failed += ch_tc.get("failed", 0)
                # Remove from uncovered anything that's covered by another change
                uncovered -= covered
                if all_cases or covered:
                    total_testable = len(covered) + len(uncovered)
                    tc = {
                        "test_cases": all_cases,
                        "covered_reqs": sorted(covered),
                        "uncovered_reqs": sorted(uncovered),
                        "non_testable_reqs": sorted(non_testable),
                        "total_tests": len(all_cases),
                        "passed": passed,
                        "failed": failed,
                        "coverage_pct": round(len(covered) / total_testable * 100, 1) if total_testable > 0 else 0,
                    }

            if tc:
                result["test_coverage"] = tc
        except (json.JSONDecodeError, OSError):
            pass

    # Section 11.3: attribute REQs to archived changes when no live-plan
    # change covers them but spec-coverage-history.jsonl says one did.
    _attribute_reqs_from_history(result, project_path, effective_lineage)

    result["effective_lineage"] = effective_lineage
    return result


@router.get("/api/{project}/digest/e2e")
def get_digest_e2e(project: str, lineage: Optional[str] = None):
    """Aggregate e2e-manifest history + live manifests for the lineage.

    Section 12.3 / AC-30: returns one block per change (live or archived),
    with `archived = true` on history-sourced entries.  AC-31: when
    history is missing, falls back to live worktree manifests only.

    Filters by `?lineage=` (default = `resolve_lineage_default`).
    """
    from .lineages import resolve_lineage_default
    project_path = _resolve_project(project)
    effective_lineage = lineage or resolve_lineage_default(project_path)

    blocks: list[dict] = []
    seen_changes: set[str] = set()

    # History blocks (archived).
    history_path = project_path / "set" / "orchestration" / "e2e-manifest-history.jsonl"
    if history_path.is_file():
        try:
            with open(history_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if effective_lineage and effective_lineage not in ("__all__", "__legacy__"):
                        rec_lineage = rec.get("spec_lineage_id") or "__legacy__"
                        if rec_lineage != effective_lineage:
                            continue
                    blocks.append({
                        "change": rec.get("change", ""),
                        "spec_lineage_id": rec.get("spec_lineage_id"),
                        "session_id": rec.get("session_id"),
                        "plan_version": rec.get("plan_version"),
                        "merged_at": rec.get("merged_at") or rec.get("ts"),
                        "manifest": rec.get("manifest", {}),
                        "archived": True,
                    })
                    seen_changes.add(rec.get("change", ""))
        except OSError as exc:
            logger.debug("digest/e2e: cannot read history: %s", exc)

    # Live blocks — scan running/done changes' worktrees for fresh manifests
    # not yet archived.
    sp = _state_path(project_path)
    if sp.exists():
        try:
            state = load_state(str(sp))
            change_lineage_map = _build_change_lineage_map(project_path, state)
            for c in state.changes:
                if c.name in seen_changes:
                    continue
                if not c.worktree_path:
                    continue
                manifest_path = os.path.join(c.worktree_path, "e2e-manifest.json")
                if not os.path.isfile(manifest_path):
                    continue
                try:
                    with open(manifest_path) as fh:
                        manifest = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    continue
                ch_lineage = change_lineage_map.get(c.name) or state.spec_lineage_id
                if effective_lineage and effective_lineage not in ("__all__", "__legacy__"):
                    if (ch_lineage or "__legacy__") != effective_lineage:
                        continue
                blocks.append({
                    "change": c.name,
                    "spec_lineage_id": ch_lineage,
                    "session_id": c.sentinel_session_id,
                    "plan_version": state.plan_version,
                    "merged_at": c.completed_at or c.started_at,
                    "manifest": manifest,
                    "archived": False,
                })
        except Exception as exc:
            logger.debug("digest/e2e: live-block enrichment failed: %s", exc)

    # Aggregate totals.
    total_tests = sum(
        len(b.get("manifest", {}).get("tests") or []) for b in blocks
    )
    total_passed = sum(
        sum(1 for t in (b.get("manifest", {}).get("tests") or []) if t.get("passed"))
        for b in blocks
    )

    return {
        "blocks": blocks,
        "total_tests": total_tests,
        "total_passed": total_passed,
        "effective_lineage": effective_lineage,
    }


def _attribute_reqs_from_history(
    result: dict, project_path: Path, effective_lineage: Optional[str],
) -> None:
    """Section 11.3 / AC-26: enrich requirements with archived attribution.

    For every REQ that has no live-plan change owning it, consult
    `spec-coverage-history.jsonl` to find the most recent merged
    change (within `effective_lineage`) that covered it.  Attach
    `merged_by` + `merged_by_archived = true` + `merged_at` so the
    Digest UI can render archived attribution.
    """
    history_path = project_path / "set" / "orchestration" / "spec-coverage-history.jsonl"
    if not history_path.is_file():
        return
    reqs = result.get("requirements")
    if not reqs:
        return
    # Locate the actual req list inside the various wrapper shapes.
    req_list = reqs
    if isinstance(reqs, list) and len(reqs) == 1 and isinstance(reqs[0], dict) \
            and "requirements" in reqs[0]:
        req_list = reqs[0]["requirements"]
    elif isinstance(reqs, dict) and "requirements" in reqs:
        req_list = reqs["requirements"]
    if not isinstance(req_list, list):
        return

    # Walk history once, building req_id → most-recent (change, merged_at).
    history_attrib: dict[str, dict] = {}
    try:
        with open(history_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Filter by lineage when one is selected.
                if effective_lineage and effective_lineage not in ("__all__", "__legacy__"):
                    rec_lineage = rec.get("spec_lineage_id") or "__legacy__"
                    if rec_lineage != effective_lineage:
                        continue
                merged_at = rec.get("merged_at") or rec.get("ts") or ""
                change = rec.get("change") or ""
                for r_id in rec.get("reqs", []) or []:
                    prev = history_attrib.get(r_id)
                    if prev is None or prev["merged_at"] < merged_at:
                        history_attrib[r_id] = {
                            "merged_by": change,
                            "merged_by_archived": True,
                            "merged_at": merged_at,
                        }
    except OSError:
        return

    if not history_attrib:
        return

    # Attach archived attribution to REQs without a live merged_by.
    for req in req_list:
        if not isinstance(req, dict):
            continue
        if req.get("merged_by"):
            continue
        rid = req.get("id") or req.get("requirement_id") or req.get("req_id")
        if not rid:
            continue
        if rid in history_attrib:
            req.update(history_attrib[rid])


def _enrich_requirements_with_scenarios(result: dict, project_path: Path):
    """Parse BDD scenarios from OpenSpec specs and attach to digest requirements.

    The connection: digest REQ → change (via state) → OpenSpec spec (via archive).
    OpenSpec specs live in openspec/specs/<capability>/spec.md and contain
    #### Scenario: blocks with WHEN/THEN format.

    Strategy:
    1. Read all OpenSpec specs from openspec/specs/
    2. Parse all scenarios from all specs
    3. Match to digest REQs by fuzzy title matching (REQ title ↔ OpenSpec requirement name)
    """
    reqs = result.get("requirements")
    if not reqs:
        return

    req_list = reqs
    if isinstance(reqs, list) and len(reqs) == 1 and isinstance(reqs[0], dict) and "requirements" in reqs[0]:
        req_list = reqs[0]["requirements"]
    elif isinstance(reqs, dict) and "requirements" in reqs:
        req_list = reqs["requirements"]

    if not isinstance(req_list, list):
        return

    try:
        from ..test_coverage import parse_scenarios
    except ImportError:
        return

    # Read all OpenSpec specs and collect scenarios keyed by requirement name (lowercased)
    openspec_dir = project_path / "openspec" / "specs"
    scenario_map: dict[str, list] = {}  # lowercase req name → scenarios

    if openspec_dir.is_dir():
        for spec_dir in sorted(openspec_dir.iterdir()):
            spec_file = spec_dir / "spec.md"
            if not spec_file.is_file():
                continue
            try:
                content = spec_file.read_text()
            except OSError:
                continue

            # Parse scenarios from each ### Requirement: section
            import re
            req_sections = re.split(r"(?=^### Requirement:\s*)", content, flags=re.MULTILINE)
            for section in req_sections:
                if not section.startswith("### Requirement:"):
                    continue
                # Extract requirement name from first line
                first_line = section.split("\n")[0]
                req_name = first_line.replace("### Requirement:", "").strip()
                scenarios = parse_scenarios(section)
                if scenarios:
                    key = req_name.lower().strip()
                    scenario_map[key] = [s.to_dict() for s in scenarios]

    # Match digest REQs to OpenSpec scenarios by fuzzy title match
    for req in req_list:
        if not isinstance(req, dict):
            continue
        title = req.get("title", "").lower().strip()
        req["scenarios"] = []

        if not title:
            continue

        # Try exact match first
        if title in scenario_map:
            req["scenarios"] = scenario_map[title]
            continue

        # Fuzzy: check if any openspec req name is contained in digest title or vice versa
        for os_name, scenarios in scenario_map.items():
            if os_name in title or title in os_name:
                req["scenarios"] = scenarios
                break
            # Word overlap: if 60%+ of words match
            title_words = set(title.split())
            os_words = set(os_name.split())
            if title_words and os_words:
                overlap = len(title_words & os_words) / min(len(title_words), len(os_words))
                if overlap >= 0.6:
                    req["scenarios"] = scenarios
                    break


@router.get("/api/{project}/coverage-report")
def get_coverage_report(project: str):
    """Return spec coverage report markdown if it exists."""
    project_path = _resolve_project(project)
    report = project_path / "set" / "orchestration" / "spec-coverage-report.md"
    if not report.exists():
        return {"exists": False}
    try:
        return {"exists": True, "content": report.read_text()}
    except OSError:
        return {"exists": False}


@router.get("/api/{project}/requirements")
def get_requirements(project: str):
    """Aggregate requirements across all plan versions with live status from state.

    Merges all plan JSON files to build a unified requirement map,
    then overlays current change status from orchestration state.
    """
    project_path = _resolve_project(project)
    plans_dir = project_path / "set" / "orchestration" / "plans"
    has_plans_dir = plans_dir.is_dir()

    # Load all plans in order
    plan_files = sorted(
        (f for f in plans_dir.iterdir() if f.is_file() and f.suffix == ".json"),
        key=lambda f: f.name,
    ) if has_plans_dir else []

    if not plan_files:
        # Fallback: build change list from live state even without plan files
        try:
            sp = _state_path(project_path)
            if sp.exists():
                state = load_state(str(sp))
                if state.changes:
                    changes_out = []
                    for ch in state.changes:
                        changes_out.append({
                            "name": ch.name,
                            "complexity": "?",
                            "change_type": "feature",
                            "depends_on": [],
                            "requirements": [],
                            "also_affects_reqs": [],
                            "scope_summary": "",
                            "plan_version": "",
                            "roadmap_item": "",
                            "status": ch.status,
                        })
                    return {
                        "requirements": [],
                        "changes": changes_out,
                        "groups": [],
                        "plan_versions": [],
                        "total_reqs": 0,
                        "done_reqs": 0,
                    }
        except Exception:
            pass
        return {"requirements": [], "changes": [], "groups": [], "plan_versions": [], "total_reqs": 0, "done_reqs": 0}

    # Build unified maps: req_id -> info, change_name -> info
    all_reqs: dict[str, dict] = {}  # req_id -> {change, plan_version, ...}
    all_changes: dict[str, dict] = {}  # change_name -> merged info
    plan_versions: list[str] = []

    for pf in plan_files:
        try:
            with open(pf) as f:
                plan = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        plan_versions.append(pf.name)
        for ch in plan.get("changes", []):
            name = ch.get("name", "")
            if not name:
                continue
            # Merge change info (later plans override)
            all_changes[name] = {
                "name": name,
                "complexity": ch.get("complexity", "?"),
                "change_type": ch.get("change_type", "feature"),
                "depends_on": ch.get("depends_on", []),
                "requirements": ch.get("requirements", []),
                "also_affects_reqs": ch.get("also_affects_reqs", []),
                "scope_summary": (ch.get("scope", "") or "")[:200],
                "plan_version": pf.name,
                "roadmap_item": ch.get("roadmap_item", ""),
            }
            for req_id in ch.get("requirements", []):
                all_reqs[req_id] = {
                    "id": req_id,
                    "change": name,
                    "primary": True,
                    "plan_version": pf.name,
                }
            for req_id in ch.get("also_affects_reqs", []):
                if req_id not in all_reqs:
                    all_reqs[req_id] = {
                        "id": req_id,
                        "change": name,
                        "primary": False,
                        "plan_version": pf.name,
                    }

    # Overlay live status from state
    change_status: dict[str, str] = {}
    try:
        sp = _state_path(project_path)
        if sp.exists():
            state = load_state(str(sp))
            for ch in state.changes:
                change_status[ch.name] = ch.status
    except Exception:
        pass

    # Enrich changes with live status
    for name, info in all_changes.items():
        info["status"] = change_status.get(name, "planned")

    # Enrich reqs with change status
    for req_id, info in all_reqs.items():
        ch_name = info["change"]
        status = change_status.get(ch_name, "planned")
        info["status"] = status

    # Group reqs by prefix (e.g. REQ-CART -> CART)
    groups: dict[str, list[dict]] = {}
    for req in all_reqs.values():
        parts = req["id"].split("-")
        # REQ-CART-006 -> CART, CART-006 -> CART
        if len(parts) >= 3 and parts[0] == "REQ":
            group = parts[1]
        elif len(parts) >= 2:
            group = parts[0]
        else:
            group = "OTHER"
        groups.setdefault(group, []).append(req)

    # Build group summaries
    group_summaries = []
    for gname, reqs in sorted(groups.items()):
        done_statuses = {"done", "merged", "completed", "skip_merged"}
        total = len(reqs)
        done = sum(1 for r in reqs if r["status"] in done_statuses)
        in_progress = sum(1 for r in reqs if r["status"] in {"running", "implementing", "verifying"})
        failed = sum(1 for r in reqs if r["status"] in {"failed", "verify-failed"})
        group_summaries.append({
            "group": gname,
            "total": total,
            "done": done,
            "in_progress": in_progress,
            "failed": failed,
            "requirements": sorted(reqs, key=lambda r: r["id"]),
        })

    return {
        "requirements": sorted(all_reqs.values(), key=lambda r: r["id"]),
        "changes": sorted(all_changes.values(), key=lambda c: c["name"]),
        "groups": group_summaries,
        "plan_versions": plan_versions,
        "total_reqs": len(all_reqs),
        "done_reqs": sum(1 for r in all_reqs.values() if r["status"] in {"done", "merged", "completed", "skip_merged"}),
    }


@router.get("/api/{project}/events")
def get_events(project: str, type: Optional[str] = Query(None), limit: int = Query(500, ge=1, le=5000)):
    """Read orchestration state events, optionally filtered by type."""
    project_path = _resolve_project(project)
    events_file = project_path / "orchestration-state-events.jsonl"
    if not events_file.exists():
        # Try new location
        events_file = project_path / "set" / "orchestration" / "orchestration-state-events.jsonl"
    if not events_file.exists():
        return {"events": []}
    events = []
    try:
        with open(events_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if type and ev.get("type") != type:
                        continue
                    events.append(ev)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return {"events": []}
    return {"events": events[-limit:]}


@router.get("/api/{project}/settings")
def get_project_settings(project: str):
    """Get project configuration and paths for the settings panel."""
    project_path = _resolve_project(project)
    result: dict = {
        "project_path": str(project_path),
        "state_path": None,
        "config": {},
        "has_claude_md": False,
        "has_project_knowledge": False,
        "runs_dir": None,
        "orchestrator_pid": None,
        "sentinel_pid": None,
        "plan_version": None,
    }

    # State file
    sp = _state_path(project_path)
    if sp.exists():
        result["state_path"] = str(sp)
        try:
            state_raw = json.loads(sp.read_text())
            result["orchestrator_pid"] = state_raw.get("orchestrator_pid")
            result["plan_version"] = state_raw.get("plan_version")
            result["orch_status"] = state_raw.get("status")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"settings: failed to read state file {sp}: {e}")

    # Sentinel PID
    sentinel_pid_file = _sentinel_dir(project_path) / "sentinel.pid"
    if sentinel_pid_file.exists():
        try:
            pid = int(sentinel_pid_file.read_text().strip())
            os.kill(pid, 0)  # check alive
            result["sentinel_pid"] = pid
        except (ValueError, OSError):
            pass

    # Orchestration config (YAML)
    for cfg_path in [
        project_path / "set" / "orchestration" / "config.yaml",
        project_path / ".claude" / "orchestration.yaml",
    ]:
        if cfg_path.exists():
            result["config_path"] = str(cfg_path)
            try:
                import yaml
                with open(cfg_path) as f:
                    result["config"] = yaml.safe_load(f) or {}
            except Exception:
                try:
                    with open(cfg_path) as f:
                        result["config_raw"] = f.read()
                except OSError:
                    pass
            break

    # CLAUDE.md
    for md in [project_path / "CLAUDE.md", project_path / ".claude" / "CLAUDE.md"]:
        if md.exists():
            result["has_claude_md"] = True
            break

    # Project knowledge
    for pk in [
        project_path / "set" / "knowledge" / "project-knowledge.yaml",
        project_path / "project-knowledge.yaml",
    ]:
        if pk.exists():
            result["has_project_knowledge"] = True
            break

    # Runs dir
    for rd in [project_path / "set" / "orchestration" / "runs", project_path / "docs" / "orchestration-runs"]:
        if rd.is_dir():
            result["runs_dir"] = str(rd)
            try:
                result["runs_count"] = sum(1 for f in rd.iterdir() if f.is_dir() or f.suffix == ".md")
            except OSError:
                pass
            break

    # Data sources: which tabs have data
    plans_dir = project_path / "set" / "orchestration" / "plans"
    plan_count = 0
    if plans_dir.is_dir():
        plan_count = sum(1 for f in plans_dir.iterdir() if f.is_file() and f.suffix == ".json")

    digest_path = project_path / "set" / "orchestration" / "digest.json"
    change_count = 0
    if sp.exists():
        try:
            state = load_state(str(sp))
            change_count = len(state.changes)
        except Exception:
            pass

    result["data_sources"] = {
        "plans": {"available": plan_count > 0, "count": plan_count},
        "digest": {"available": digest_path.exists()},
        "state": {"available": sp.exists(), "changes": change_count},
        "orchestration_config": {"available": "config_path" in result},
    }

    return result


# ─── Memory endpoints ────────────────────────────────────────────────


def _run_wt_memory(project_path: Path, args: list[str], timeout: int = 10) -> dict | str:
    """Run set-memory CLI with project-scoped CWD, return parsed JSON or raw string."""
    try:
        result = subprocess.run(
            ["set-memory"] + args,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(project_path),
        )
        out = result.stdout.strip()
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "set-memory failed"}
        try:
            return json.loads(out)
        except (json.JSONDecodeError, TypeError):
            return out
    except FileNotFoundError:
        return {"error": "set-memory not found"}
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s"}


@router.get("/api/{project}/memory")
def get_memory_overview(project: str):
    """Aggregate memory stats, health, and sync status in a single call."""
    project_path = _resolve_project(project)

    # Run all three set-memory commands in parallel (was sequential → 3-5s+ first load)
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_health = pool.submit(_run_wt_memory, project_path, ["health"])
        f_stats = pool.submit(_run_wt_memory, project_path, ["stats", "--json"])
        f_sync = pool.submit(_run_wt_memory, project_path, ["sync", "status"])

        health = f_health.result()
        stats = f_stats.result()
        sync = f_sync.result()

    return {
        "health": health if isinstance(health, str) else health,
        "stats": stats if isinstance(stats, dict) else {},
        "sync": sync if isinstance(sync, str) else str(sync),
    }


@router.get("/api/{project}/llm-calls")
def get_llm_calls(
    project: str,
    limit: int = Query(500, ge=1, le=5000),
    lineage: Optional[str] = None,
):
    """Chronological list of all LLM calls: events JSONL + session files.

    Combines two sources:
    1. LLM_CALL events from orchestration events JSONL (review, decompose, digest, etc.)
    2. Claude session files per change (implementation sessions with full token data)

    Returns sorted by timestamp, most recent first.

    Section 13.4: when `?lineage=` is provided, only calls attributable to
    that lineage are returned.  Attribution comes from the change's
    persisted `spec_lineage_id` (live state or archive); calls without an
    attributable change pass through under `__legacy__`.
    """
    project_path = _resolve_project(project)
    calls: list[dict] = []

    # Source 1: LLM_CALL events from events JSONL
    _read_llm_call_events(project_path, calls)

    # Source 2: Session files across all changes (+ project-level even without state)
    sp = _state_path(project_path)
    state = None
    if sp.exists():
        try:
            state = load_state(str(sp))
        except Exception:
            pass
    # Collect event-source purpose+change pairs for dedup
    event_keys = {(c["purpose_raw"], c["change"]) for c in calls if c["source"] == "orchestration"}
    _read_session_calls(state, project_path, calls, skip_keys=event_keys)

    # Section 13.4 — apply lineage filter via per-change lineage map.
    from .lineages import apply_lineage_filter, resolve_lineage_default
    effective_lineage = lineage or resolve_lineage_default(project_path)
    if effective_lineage and effective_lineage != "__all__":
        change_lineage = _build_change_lineage_map(project_path, state)
        # Tag every call with its change's lineage (default __legacy__).
        for c in calls:
            c["spec_lineage_id"] = change_lineage.get(c.get("change", ""), "__legacy__")
        calls = apply_lineage_filter(calls, effective_lineage)

    # Sort chronologically (most recent first) and limit
    calls.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
    return {"calls": calls[:limit], "effective_lineage": effective_lineage}


def _build_change_lineage_map(project_path: Path, state) -> dict[str, str]:
    """Return {change_name: spec_lineage_id} from live state + archive."""
    out: dict[str, str] = {}
    if state is not None:
        for c in state.changes:
            lid = c.spec_lineage_id or state.spec_lineage_id
            if lid:
                out[c.name] = lid
    archived = _load_archived_changes(project_path)
    for entry in archived:
        lid = entry.get("spec_lineage_id")
        if lid and entry.get("name") not in out:
            out[entry["name"]] = lid
    return out


def _read_llm_call_events(project_path: Path, calls: list[dict]) -> None:
    """Read LLM_CALL events from ALL orchestration event files, live + rotated.

    Section 4.2 of run-history-and-phase-continuity: include
    `orchestration-events-cycle*.jsonl` and the state-events siblings so
    LLM-calls history survives replan rotation.  Calls are deduplicated
    by `(ts, change, purpose)` because both the runtime event_bus and the
    engine's _emit_event can emit the same LLM_CALL row.
    """
    import glob as _glob
    import re as _re

    def _cycle_key(p: str) -> tuple:
        m = _re.search(r"-cycle(\d+)\.jsonl$", p.rsplit("/", 1)[-1])
        return (1, int(m.group(1))) if m else (0, p)

    # Resolve runtime events path (where event_bus singleton writes before engine sync)
    runtime_events = None
    try:
        from ..paths import SetRuntime
        rt = SetRuntime(str(project_path))
        runtime_events = Path(rt.events_file)
    except Exception:
        pass

    base_dirs = [
        project_path,
        project_path / "set" / "orchestration",
    ]
    # Include the runtime dir so rotated cycle files written there are picked up.
    if runtime_events is not None:
        base_dirs.append(Path(runtime_events).parent)

    candidates: list[Path] = []
    for base in base_dirs:
        for stem in ("orchestration-events", "orchestration-state-events"):
            cycle_pattern = str(base / f"{stem}-cycle*.jsonl")
            for f in sorted(_glob.glob(cycle_pattern), key=_cycle_key):
                candidates.append(Path(f))
            live = base / f"{stem}.jsonl"
            if live.exists() and live not in candidates:
                candidates.append(live)
    if runtime_events and runtime_events not in candidates:
        candidates.append(runtime_events)

    # Collect into a temporary list, then dedup by (ts, change, purpose_raw).
    raw_calls: list[dict] = []
    for events_file in candidates:
        if not events_file.exists():
            continue
        _parse_llm_events_file(events_file, raw_calls)

    seen: set[tuple] = set()
    for c in raw_calls:
        key = (c.get("timestamp", ""), c.get("change", ""), c.get("purpose_raw", ""))
        if key in seen:
            continue
        seen.add(key)
        calls.append(c)


def _parse_llm_events_file(events_file: Path, calls: list[dict]) -> None:
    """Parse LLM_CALL events from a single JSONL file."""
    try:
        with open(events_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") != "LLM_CALL":
                    continue
                data = ev.get("data", {})
                calls.append({
                    "timestamp": ev.get("ts", ""),
                    "source": "orchestration",
                    "purpose": _PURPOSE_LABELS.get(
                        data.get("purpose", ""), data.get("purpose", "unknown")
                    ),
                    "purpose_raw": data.get("purpose", ""),
                    "model": data.get("model", "default"),
                    "change": ev.get("change", ""),
                    "duration_ms": data.get("duration_ms", 0),
                    "input_tokens": (
                        data.get("input_tokens", 0)
                        + data.get("cache_read_tokens", 0)
                        + data.get("cache_create_tokens", 0)
                    ),
                    "output_tokens": data.get("output_tokens", 0),
                    "cache_tokens": data.get("cache_read_tokens", 0),
                    "exit_code": data.get("exit_code", 0),
                    "active": False,
                })
    except OSError:
        pass


def _read_session_calls(state, project_path: Path, calls: list[dict], skip_keys: set | None = None) -> None:
    """Read Claude session files for all changes + project-level orchestration sessions."""
    from .sessions import (
        _extract_session_model,
        _extract_session_tokens,
        _derive_session_label,
        _extract_session_change_name,
    )

    seen_ids: set[str] = set()

    # Build list of (session_dir, change_name_or_empty) pairs
    dir_change_pairs: list[tuple[Path, str]] = []

    # Project-level sessions (digest, decompose, sentinel — not change-specific)
    proj_mangled = _claude_mangle(str(project_path))
    proj_dir = Path.home() / ".claude" / "projects" / f"-{proj_mangled}"
    if proj_dir.is_dir():
        dir_change_pairs.append((proj_dir, ""))

    # Per-change worktree sessions (only if state is available)
    if state is not None:
        for change in state.changes:
            if change.worktree_path:
                mangled = _claude_mangle(change.worktree_path)
                d = Path.home() / ".claude" / "projects" / f"-{mangled}"
                if d.is_dir():
                    dir_change_pairs.append((d, change.name))

    for d, default_change in dir_change_pairs:
        try:
            for f in d.iterdir():
                if not f.is_file() or f.suffix != ".jsonl":
                    continue
                if f.stem in seen_ids:
                    continue
                seen_ids.add(f.stem)
                try:
                    st = f.stat()
                    label, _full = _derive_session_label(f)
                    model = _extract_session_model(f)
                    tokens = _extract_session_tokens(f)
                    duration_ms = _session_duration_ms(f)

                    # Determine change name
                    change_name = default_change
                    if not change_name:
                        # Project-dir session — try to extract change from content
                        change_name = _extract_session_change_name(f)

                    # Effective input = input + cache_read + cache_create
                    eff_input = (
                        tokens.get("input_tokens", 0)
                        + tokens.get("cache_read_tokens", 0)
                        + tokens.get("cache_create_tokens", 0)
                    )

                    is_active = (time.time() - st.st_mtime) < 60

                    # Skip if we already have an event-source entry for this purpose+change
                    raw_purpose = label.lower().replace(" ", "_")
                    if skip_keys and (raw_purpose, change_name or "") in skip_keys:
                        continue

                    # Use local-with-offset timestamp to match event-sourced
                    # rows (event_bus writes datetime.now(UTC).astimezone()).
                    # The frontend displays the ISO string verbatim without
                    # timezone conversion, so we must emit local time with
                    # the offset suffix — emitting naive UTC here would
                    # cause session rows to render 1-2h earlier than they
                    # actually happened vs event-sourced rows.
                    calls.append({
                        "timestamp": datetime.fromtimestamp(
                            st.st_mtime, tz=timezone.utc
                        ).astimezone().isoformat(),
                        "source": "session",
                        "purpose": label,
                        "purpose_raw": label.lower().replace(" ", "_"),
                        "model": model or "unknown",
                        "change": change_name or "",
                        "duration_ms": duration_ms,
                        "input_tokens": eff_input,
                        "output_tokens": tokens.get("output_tokens", 0),
                        "cache_tokens": tokens.get("cache_read_tokens", 0),
                        "exit_code": 0,
                        "active": is_active,
                    })
                except OSError:
                    pass
        except OSError:
            pass

    # Section 10.2 — synthesize aggregate `archive_summary` calls for
    # archived changes whose worktree session dir is gone.  Each archive
    # entry's `session_summary` becomes one synthetic call so the
    # Tokens / LLM-calls panel can render the change after cleanup.
    archived = _load_archived_changes(project_path)
    seen_archive: set[str] = set()
    for entry in archived:
        name = entry.get("name", "")
        summary = entry.get("session_summary") or {}
        if not name or not summary or name in seen_archive:
            continue
        if not (summary.get("call_count") or summary.get("input_tokens")):
            continue
        wt = entry.get("worktree_path")
        # Only emit the synthetic call when the live session dir is
        # absent — otherwise the per-file loop above already covered it.
        if wt:
            mangled = _claude_mangle(wt)
            if (Path.home() / ".claude" / "projects" / f"-{mangled}").is_dir():
                continue
        seen_archive.add(name)
        ts = summary.get("last_call_ts") or entry.get("archived_at") or ""
        calls.append({
            "timestamp": ts,
            "source": "archive_summary",
            "purpose": "aggregated",
            "purpose_raw": "aggregated",
            "model": "archived",
            "change": name,
            "duration_ms": int(summary.get("total_duration_ms", 0) or 0),
            "input_tokens": int(summary.get("input_tokens", 0) or 0)
                            + int(summary.get("cache_read_tokens", 0) or 0)
                            + int(summary.get("cache_create_tokens", 0) or 0),
            "output_tokens": int(summary.get("output_tokens", 0) or 0),
            "cache_tokens": int(summary.get("cache_read_tokens", 0) or 0),
            "exit_code": 0,
            "active": False,
            "spec_lineage_id": entry.get("spec_lineage_id"),
        })


def _session_duration_ms(path: Path) -> int:
    """Estimate session duration from first and last JSONL entry timestamps."""
    first_ts = None
    last_ts = None
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = entry.get("timestamp")
                if not ts:
                    continue
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
    except OSError:
        return 0
    if first_ts and last_ts and first_ts != last_ts:
        try:
            # Timestamps may be ISO format or epoch
            t1 = _parse_ts(first_ts)
            t2 = _parse_ts(last_ts)
            if t1 and t2:
                return max(0, int((t2 - t1) * 1000))
        except (ValueError, TypeError):
            pass
    return 0


def _parse_ts(ts) -> float | None:
    """Parse a timestamp (ISO string or epoch float) to epoch seconds."""
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None
