"""Orchestration state, changes, plans, digest, coverage, requirements, settings, memory routes."""

from __future__ import annotations

import json
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

router = APIRouter()

@router.get("/api/{project}/state")
def get_state(project: str):
    """Get full orchestration state for a project."""
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
                "mtime": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
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
def get_digest(project: str):
    """Return digest data: index, requirements, coverage, domains, dependencies, ambiguities."""
    project_path = _resolve_project(project)
    digest_dir = project_path / "set" / "orchestration" / "digest"
    if not digest_dir.is_dir():
        return {"exists": False}

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

    return result


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
            state = load_state(str(sp))
            result["orchestrator_pid"] = state.orchestrator_pid
            result["plan_version"] = state.plan_version
            result["orch_status"] = state.status
        except Exception:
            pass

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
def get_llm_calls(project: str, limit: int = Query(500, ge=1, le=5000)):
    """Chronological list of all LLM calls: events JSONL + session files.

    Combines two sources:
    1. LLM_CALL events from orchestration events JSONL (review, decompose, digest, etc.)
    2. Claude session files per change (implementation sessions with full token data)

    Returns sorted by timestamp, most recent first.
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

    # Sort chronologically (most recent first) and limit
    calls.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
    return {"calls": calls[:limit]}


def _read_llm_call_events(project_path: Path, calls: list[dict]) -> None:
    """Read LLM_CALL events from ALL orchestration events JSONL files.

    Two files may exist: orchestration-state-events.jsonl (engine._emit_event)
    and orchestration-events.jsonl (event_bus from run_claude_logged).
    """
    # Resolve runtime events path (where event_bus singleton writes before engine sync)
    runtime_events = None
    try:
        from ..paths import SetRuntime
        rt = SetRuntime(str(project_path))
        runtime_events = Path(rt.events_file)
    except Exception:
        pass

    candidates = [
        project_path / "orchestration-state-events.jsonl",
        project_path / "set" / "orchestration" / "orchestration-state-events.jsonl",
        project_path / "orchestration-events.jsonl",
        project_path / "set" / "orchestration" / "orchestration-events.jsonl",
    ]
    if runtime_events and runtime_events not in candidates:
        candidates.append(runtime_events)
    for events_file in candidates:
        if not events_file.exists():
            continue
        _parse_llm_events_file(events_file, calls)


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

                    calls.append({
                        "timestamp": datetime.fromtimestamp(
                            st.st_mtime, tz=timezone.utc
                        ).isoformat(),
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
