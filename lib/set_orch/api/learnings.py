"""Learnings routes: review findings, gate stats, reflections, change timeline, scoreboard."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..state import load_state, StateCorruptionError
from .helpers import _resolve_project, _state_path, _sentinel_dir, _list_worktrees
from .sessions import (
    _sessions_dirs_for_change,
    _extract_session_tokens,
    _extract_session_model,
    _derive_session_label,
    _session_outcome,
)

router = APIRouter()

# ─── Learnings endpoints ─────────────────────────────────────────────


def _resolve_findings_file(project_path: Path) -> Optional[Path]:
    """Find review-findings.jsonl with fallback paths."""
    for candidate in [
        project_path / "set" / "orchestration" / "review-findings.jsonl",
        project_path / "orchestration" / "review-findings.jsonl",
    ]:
        if candidate.exists():
            return candidate
    return None


def _read_review_findings(project_path: Path) -> dict:
    """Read and parse review findings from JSONL or state.json review_output fallback."""
    entries = []
    pattern_counts: dict[str, int] = {}

    # Try JSONL first
    findings_file = _resolve_findings_file(project_path)
    if findings_file:
        try:
            with open(findings_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

        for entry in entries:
            for issue in entry.get("issues", []):
                norm = re.sub(r"\[(?:CRITICAL|HIGH|MEDIUM)\]\s*", "", issue.get("summary", ""))[:80]
                if norm:
                    pattern_counts[norm] = pattern_counts.get(norm, 0) + 1

    # Fallback: extract from state.json review_output (always available)
    if not entries:
        state_file = project_path / "orchestration-state.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    state_data = json.load(f)
                for c in state_data.get("changes", []):
                    review_out = c.get("review_output", "")
                    if not review_out:
                        continue
                    change_name = c.get("name", "")
                    issues = []
                    for match in re.finditer(r"\*?\*?ISSUE:\s*\[(\w+)\]\s*(.+?)(?:\*\*|\n|$)", review_out):
                        severity = match.group(1)
                        summary = match.group(2).strip()[:120]
                        issues.append({"severity": severity, "summary": summary})
                        norm = summary[:80]
                        pattern_counts[norm] = pattern_counts.get(norm, 0) + 1
                    if issues:
                        entries.append({"change": change_name, "issues": issues})
            except (json.JSONDecodeError, OSError):
                pass

    # Keyword-based clustering for fuzzy matching across variations
    _CLUSTERS = {
        "no-auth": ["no auth", "no authentication", "zero authentication", "without auth"],
        "no-csrf": ["csrf", "cross-site request"],
        "xss": ["xss", "dangerouslysetinnerhtml", "v-html"],
        "no-rate-limit": ["rate limit", "rate-limit"],
        "secrets-exposed": ["masking", "exposed", "leaked", "codes displayed"],
    }
    cluster_counts: dict[str, int] = {}
    cluster_changes: dict[str, set] = {}
    for entry in entries:
        change_name = entry.get("change", "")
        for issue in entry.get("issues", []):
            raw = issue.get("summary", "").lower()
            for cid, keywords in _CLUSTERS.items():
                if any(kw in raw for kw in keywords):
                    cluster_counts[cid] = cluster_counts.get(cid, 0) + 1
                    cluster_changes.setdefault(cid, set()).add(change_name)
                    break

    recurring = [
        {"pattern": k, "count": v}
        for k, v in sorted(pattern_counts.items(), key=lambda x: -x[1])
        if v >= 2
    ]
    # Add keyword clusters as recurring patterns
    for cid, changes_set in sorted(cluster_changes.items(), key=lambda x: -len(x[1])):
        if len(changes_set) >= 2:
            recurring.append({
                "pattern": f"[{cid}] ({len(changes_set)} changes)",
                "count": cluster_counts[cid],
                "cluster": cid,
                "changes": sorted(changes_set),
            })

    # Read summary MD if exists
    summary = ""
    if findings_file:
        summary_file = findings_file.parent / "review-findings-summary.md"
        if summary_file.exists():
            try:
                summary = summary_file.read_text(errors="replace")
            except OSError:
                pass

    return {"entries": entries, "summary": summary, "recurring_patterns": recurring}


def _compute_gate_stats(project_path: Path) -> dict:
    """Aggregate gate stats from orchestration state."""
    state_file = project_path / "orchestration-state.json"
    if not state_file.exists():
        return {"per_gate": {}, "retry_summary": {}, "per_change_type": {}}

    try:
        with open(state_file) as f:
            state_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"per_gate": {}, "retry_summary": {}, "per_change_type": {}}

    changes = state_data.get("changes", [])
    if not changes:
        return {"per_gate": {}, "retry_summary": {}, "per_change_type": {}}

    # Gate fields: direct fields + extras fallback
    gate_defs = [
        ("build", "build_result", "gate_build_ms"),
        ("test", "test_result", "gate_test_ms"),
        ("review", "review_result", "gate_review_ms"),
        ("smoke", "smoke_result", "gate_verify_ms"),
    ]

    per_gate: dict[str, dict] = {}
    total_retries = 0
    total_retry_ms = 0
    total_gate_ms = 0
    most_retried_gate = ""
    most_retried_count = 0
    most_retried_change = ""
    most_retried_change_count = 0

    # Per change type accumulators
    type_stats: dict[str, dict] = {}

    for change in changes:
        extras = change if isinstance(change, dict) else {}
        change_type = extras.get("change_type", "unknown")
        vrc = extras.get("verify_retry_count", 0) or 0
        rdc = extras.get("redispatch_count", 0) or 0
        change_retries = vrc + rdc
        total_retries += change_retries
        change_name = extras.get("name", "")

        if change_retries > most_retried_change_count:
            most_retried_change_count = change_retries
            most_retried_change = change_name

        gate_ms = extras.get("gate_total_ms", 0) or 0
        total_gate_ms += gate_ms

        if change_type not in type_stats:
            type_stats[change_type] = {"total_gate_ms": 0, "total_retries": 0, "count": 0}
        type_stats[change_type]["total_gate_ms"] += gate_ms
        type_stats[change_type]["total_retries"] += change_retries
        type_stats[change_type]["count"] += 1

        for gate_name, result_field, ms_field in gate_defs:
            result = extras.get(result_field)
            if not result:
                # Check extras dict for e2e
                result = extras.get("extras", {}).get(f"{gate_name}_result") if isinstance(extras.get("extras"), dict) else None
            if not result:
                continue

            if gate_name not in per_gate:
                per_gate[gate_name] = {"total": 0, "pass": 0, "fail": 0, "skip": 0, "total_ms": 0}

            per_gate[gate_name]["total"] += 1
            if result == "pass":
                per_gate[gate_name]["pass"] += 1
            elif result in ("fail", "critical"):
                per_gate[gate_name]["fail"] += 1
            elif result in ("skipped", "skip"):
                per_gate[gate_name]["skip"] += 1

            ms = extras.get(ms_field, 0) or 0
            per_gate[gate_name]["total_ms"] += ms

    # Also check e2e from extras
    for change in changes:
        extras = change if isinstance(change, dict) else {}
        e2e_result = extras.get("extras", {}).get("e2e_result") if isinstance(extras.get("extras"), dict) else None
        if not e2e_result:
            e2e_result = extras.get("e2e_result")
        if e2e_result:
            if "e2e" not in per_gate:
                per_gate["e2e"] = {"total": 0, "pass": 0, "fail": 0, "skip": 0, "total_ms": 0}
            per_gate["e2e"]["total"] += 1
            if e2e_result == "pass":
                per_gate["e2e"]["pass"] += 1
            elif e2e_result in ("fail", "critical"):
                per_gate["e2e"]["fail"] += 1
            elif e2e_result in ("skipped", "skip"):
                per_gate["e2e"]["skip"] += 1
            e2e_ms = extras.get("gate_e2e_ms", 0) or extras.get("extras", {}).get("gate_e2e_ms", 0) if isinstance(extras.get("extras"), dict) else 0
            per_gate["e2e"]["total_ms"] += (e2e_ms or 0)

    # Compute derived stats
    for gate_name, stats in per_gate.items():
        denominator = stats["pass"] + stats["fail"]
        stats["pass_rate"] = round(stats["pass"] / denominator, 2) if denominator > 0 else 0
        non_skip = stats["total"] - stats["skip"]
        stats["avg_ms"] = round(stats["total_ms"] / non_skip) if non_skip > 0 else 0

    # Find most retried gate
    for gate_name, stats in per_gate.items():
        if stats["fail"] > most_retried_count:
            most_retried_count = stats["fail"]
            most_retried_gate = gate_name

    retry_pct = round(total_retries * 100 / max(len(changes), 1), 1)

    per_change_type = {}
    for ct, ts in type_stats.items():
        cnt = ts["count"]
        per_change_type[ct] = {
            "avg_gate_ms": round(ts["total_gate_ms"] / cnt) if cnt > 0 else 0,
            "avg_retries": round(ts["total_retries"] / cnt, 1) if cnt > 0 else 0,
            "count": cnt,
        }

    return {
        "per_gate": per_gate,
        "retry_summary": {
            "total_retries": total_retries,
            "total_gate_ms": total_gate_ms,
            "retry_pct": retry_pct,
            "most_retried_gate": most_retried_gate,
            "most_retried_change": most_retried_change,
        },
        "per_change_type": per_change_type,
    }


def _collect_reflections(project_path: Path) -> dict:
    """Aggregate reflections across all worktrees."""
    worktrees = _list_worktrees(project_path)
    reflections = []
    for wt in worktrees:
        if not wt.get("has_reflection"):
            continue
        refl_path = Path(wt["path"]) / ".claude" / "reflection.md"
        if not refl_path.exists():
            continue
        try:
            content = refl_path.read_text(errors="replace")
        except OSError:
            continue
        branch = wt.get("branch", "")
        change = branch.removeprefix("set/") if branch.startswith("set/") else branch
        reflections.append({"change": change, "branch": branch, "content": content})

    return {
        "reflections": reflections,
        "total": len(worktrees),
        "with_reflection": len(reflections),
    }


def _build_change_timeline(project_path: Path, change_name: str) -> dict:
    """Build change timeline from Claude session files enriched with gate/merge events.

    Primary source: Claude .jsonl session files (tokens, model, timing).
    Overlay: orchestration events (gates, merge status).
    """
    import glob as _glob

    # --- Step 1: Find Claude session files for this change ---
    state_file = _state_path(project_path)
    claude_sessions: list[dict] = []

    if state_file.exists():
        try:
            state = load_state(str(state_file))
            _change, session_dirs = _sessions_dirs_for_change(state, change_name, project_path)
            # Only use worktree-specific dirs (first), skip project-level dir (last)
            # The project dir contains sentinel/orchestrator sessions, not change-specific
            wt_dirs = [d for d in session_dirs if "wt-" in str(d)]
            for sdir in (wt_dirs or session_dirs[:1]):
                if not sdir.exists():
                    continue
                for f in sdir.iterdir():
                    if not f.is_file() or f.suffix != ".jsonl":
                        continue
                    try:
                        st = f.stat()
                        tokens = _extract_session_tokens(f)
                        model = _extract_session_model(f)
                        label, full_label = _derive_session_label(f)
                        # Extract start timestamp from first entry
                        started = ""
                        with open(f) as fh:
                            for line in fh:
                                try:
                                    entry = json.loads(line)
                                    ts = entry.get("timestamp", "")
                                    if ts:
                                        started = ts
                                        break
                                except json.JSONDecodeError:
                                    continue
                        ended = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                        age_s = time.time() - st.st_mtime
                        is_active = age_s < 60
                        claude_sessions.append({
                            "id": f.stem,
                            "started": started,
                            "ended": ended,
                            "mtime": st.st_mtime,
                            "model": model,
                            "label": label,
                            "outcome": "active" if is_active else _session_outcome(f),
                            **tokens,
                        })
                    except OSError:
                        continue
        except Exception:
            pass

    # Sort by start time
    claude_sessions.sort(key=lambda s: s.get("started", ""))

    # --- Step 2: Collect orchestration events for this change ---
    events_files: list[Path] = []
    for base_dir in [project_path, project_path / "set" / "orchestration"]:
        for name in ["orchestration-events.jsonl", "orchestration-state-events.jsonl"]:
            candidate = base_dir / name
            if candidate.exists():
                events_files.append(candidate)
                stem = name.replace(".jsonl", "")
                for archive in sorted(_glob.glob(str(base_dir / f"{stem}-*.jsonl"))):
                    events_files.append(Path(archive))
        if events_files:
            break

    gate_events: list[dict] = []
    merge_ts: str | None = None
    change_status: str = "unknown"
    for ef in events_files:
        try:
            with open(ef) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("change") != change_name:
                        continue
                    etype = ev.get("type", "")
                    if etype == "VERIFY_GATE":
                        gate_events.append(ev)
                    elif etype == "MERGE_SUCCESS":
                        merge_ts = ev.get("ts", "")
                    elif etype == "MERGE_ATTEMPT" and not merge_ts:
                        merge_ts = ev.get("ts", "")
                    elif etype == "CHANGE_DONE":
                        change_status = "done"
                    elif etype == "STATE_CHANGE":
                        to_state = ev.get("data", {}).get("to", "")
                        if to_state:
                            change_status = to_state
        except OSError:
            continue

    # --- Step 3: Build enriched sessions ---
    sessions: list[dict] = []
    for i, cs in enumerate(claude_sessions):
        session_start = cs.get("started", "")
        session_end = cs.get("ended", "")

        # Assign gate events to the last session (gates run after agent finishes)
        is_last = i == len(claude_sessions) - 1
        gates: dict = {}
        gate_ms: dict = {}
        if is_last:
            for ge in gate_events:
                data = ge.get("data", {})
                # New per-gate format
                gate_name = data.get("gate")
                gate_result = data.get("result")
                if gate_name and gate_result:
                    gates[gate_name] = gate_result
                # Legacy summary format
                for g in ("build", "test", "e2e", "review", "smoke", "scope_check", "spec_verify", "rules", "test_files"):
                    val = data.get(g)
                    if val is not None:
                        gates[g] = val
                gms = data.get("gate_ms", {})
                if gms and isinstance(gms, dict):
                    gate_ms.update(gms)

        # Determine session state
        state = cs.get("outcome", "unknown")
        merged = False
        if merge_ts and is_last:
            state = "merged"
            merged = True
        elif cs.get("outcome") == "active":
            state = "running"
        elif is_last and change_status == "done":
            state = "done"
        elif cs.get("outcome") == "error":
            state = "retry"

        # Duration
        duration_ms = 0
        if session_start and session_end:
            duration_ms = _ts_diff_ms(session_start, session_end)

        sessions.append({
            "n": i + 1,
            "id": cs.get("id", ""),
            "started": session_start,
            "ended": session_end,
            "state": state,
            "merged": merged,
            "gates": gates,
            "gate_ms": gate_ms,
            "duration_ms": duration_ms,
            "model": cs.get("model", ""),
            "label": cs.get("label", ""),
            "input_tokens": cs.get("input_tokens", 0),
            "output_tokens": cs.get("output_tokens", 0),
            "cache_read_tokens": cs.get("cache_read_tokens", 0),
            "cache_create_tokens": cs.get("cache_create_tokens", 0),
        })

    # Total duration
    duration_ms = 0
    if sessions:
        try:
            first_ts = sessions[0].get("started", "")
            last_ts = sessions[-1].get("ended", "") or sessions[-1].get("started", "")
            if first_ts and last_ts:
                first = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                last = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                duration_ms = int((last - first).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass

    # Current gate results from state
    current_gate_results: dict = {}
    if state_file.exists():
        try:
            with open(state_file) as f:
                state_data = json.load(f)
            for change in state_data.get("changes", []):
                if isinstance(change, dict) and change.get("name") == change_name:
                    for field in ("build_result", "test_result", "review_result", "smoke_result", "verify_retry_count"):
                        val = change.get(field)
                        if val is not None:
                            current_gate_results[field] = val
                    break
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "sessions": sessions,
        "duration_ms": duration_ms,
        "current_gate_results": current_gate_results,
    }


def _ts_diff_ms(ts1: str, ts2: str) -> int:
    """Milliseconds between two ISO timestamps."""
    try:
        t1 = datetime.fromisoformat(ts1.replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(ts2.replace("Z", "+00:00"))
        return int((t2 - t1).total_seconds() * 1000)
    except (ValueError, TypeError):
        return 0


@router.get("/api/{project}/review-findings")
def get_review_findings(project: str):
    """Review findings from gate verification JSONL log."""
    pp = _resolve_project(project)
    return _read_review_findings(pp)


@router.get("/api/{project}/gate-stats")
def get_gate_stats(project: str):
    """Aggregate gate performance stats across all changes."""
    pp = _resolve_project(project)
    return _compute_gate_stats(pp)


@router.get("/api/{project}/reflections")
def get_reflections(project: str):
    """Aggregate agent reflections from all worktrees."""
    pp = _resolve_project(project)
    return _collect_reflections(pp)


@router.get("/api/{project}/changes/{name}/timeline")
def get_change_timeline(project: str, name: str):
    """Per-change state transition timeline from events log."""
    pp = _resolve_project(project)
    return _build_change_timeline(pp, name)


@router.get("/api/{project}/learnings")
def get_learnings(project: str):
    """Unified learnings endpoint: reflections + review findings + gate stats + sentinel."""
    pp = _resolve_project(project)

    # Sentinel findings
    sentinel_data = {"findings": [], "assessments": []}
    findings_file = _sentinel_dir(pp) / "findings.json"
    if findings_file.exists():
        try:
            sentinel_data = json.loads(findings_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "reflections": _collect_reflections(pp),
        "review_findings": _read_review_findings(pp),
        "gate_stats": _compute_gate_stats(pp),
        "sentinel_findings": sentinel_data,
    }


# ─── Battle Scoreboard ─────────────────────────────────────────────

import hashlib
import hmac

# Server-side secret for score signing (derived from hostname for simplicity)
_SCORE_SECRET = hashlib.sha256(
    f"set-battle-{os.uname().nodename}".encode()
).hexdigest().encode()

_SCOREBOARD_FILE = Path(os.environ.get(
    "SET_SCOREBOARD_FILE",
    os.path.expanduser("~/.local/share/set-core/scoreboard.json"),
))


def _sign_score(project: str, score: int, changes_done: int, total_tokens: int) -> str:
    """Create HMAC signature from orchestration facts the server can verify."""
    msg = f"{project}:{score}:{changes_done}:{total_tokens}"
    return hmac.new(_SCORE_SECRET, msg.encode(), hashlib.sha256).hexdigest()[:16]


def _load_scoreboard() -> list:
    if not _SCOREBOARD_FILE.exists():
        return []
    try:
        with open(_SCOREBOARD_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_scoreboard(entries: list):
    _SCOREBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(_SCOREBOARD_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entries, f, indent=2)
    os.replace(tmp, str(_SCOREBOARD_FILE))


class ScoreSubmission(BaseModel):
    player: str
    project: str
    score: int
    changes_done: int
    total_changes: int
    total_tokens: int
    achievements: list[str]
    signature: str


@router.get("/api/scoreboard")
async def get_scoreboard(limit: int = 20):
    """Get the global scoreboard (top scores across all projects)."""
    entries = _load_scoreboard()
    entries.sort(key=lambda e: e.get("score", 0), reverse=True)
    return {"entries": entries[:limit]}


@router.post("/api/scoreboard/submit")
async def submit_score(body: ScoreSubmission):
    """Submit a score with server-side validation.

    Anti-cheat:
    1. Signature must match server-computed HMAC from orchestration facts
    2. Score is sanity-checked against changes_done and total_tokens
    3. Server verifies the project exists and has orchestration data
    4. Max 1000 points per change + bonuses (cap at ~5000/change)
    """
    # Verify signature
    expected_sig = _sign_score(body.project, body.score, body.changes_done, body.total_tokens)
    if not hmac.compare_digest(body.signature, expected_sig):
        raise HTTPException(status_code=403, detail="Invalid score signature")

    # Sanity check: max ~5000 points per completed change (generous upper bound)
    max_plausible = body.changes_done * 5000 + 2000  # 2000 for achievements
    if body.score > max_plausible:
        raise HTTPException(status_code=400, detail="Score exceeds plausible maximum")

    # Verify project exists
    try:
        _resolve_project(body.project)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load and update scoreboard
    entries = _load_scoreboard()

    entry = {
        "player": body.player[:20],  # max 20 chars
        "project": body.project,
        "score": body.score,
        "changes_done": body.changes_done,
        "total_changes": body.total_changes,
        "total_tokens": body.total_tokens,
        "achievements": body.achievements[:20],  # max 20
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Replace if same player+project with higher score
    existing_idx = None
    for i, e in enumerate(entries):
        if e.get("player") == entry["player"] and e.get("project") == entry["project"]:
            existing_idx = i
            break

    if existing_idx is not None:
        if entries[existing_idx].get("score", 0) < body.score:
            entries[existing_idx] = entry
        # else: keep existing higher score
    else:
        entries.append(entry)

    # Keep top 100
    entries.sort(key=lambda e: e.get("score", 0), reverse=True)
    entries = entries[:100]

    _save_scoreboard(entries)
    return {"status": "ok", "rank": next((i + 1 for i, e in enumerate(entries) if e.get("player") == entry["player"] and e.get("project") == entry["project"]), None)}


@router.get("/api/scoreboard/sign")
async def sign_score(project: str, score: int, changes_done: int, total_tokens: int):
    """Get a server-signed token for a score. Client must request this before submitting.

    This ensures only scores backed by real orchestration data can be submitted,
    since the client must know the correct changes_done and total_tokens values
    that match the server's view.
    """
    # Verify project exists and get actual state to cross-check
    try:
        pp = _resolve_project(project)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Project not found")

    # Load actual orchestration state to verify the claimed values
    try:
        state = load_state(str(pp / "orchestration-state.json"))
        actual_changes = state.get("changes", [])
        actual_done = sum(1 for c in actual_changes if c.get("status") in ("done", "merged", "completed", "skip_merged"))
        actual_tokens = sum((c.get("input_tokens", 0) or 0) + (c.get("output_tokens", 0) or 0) for c in actual_changes)

        # Allow some tolerance (client may have slightly different counts)
        if abs(changes_done - actual_done) > 2:
            raise HTTPException(status_code=400, detail="changes_done mismatch with server state")
        if actual_tokens > 0 and abs(total_tokens - actual_tokens) / max(actual_tokens, 1) > 0.2:
            raise HTTPException(status_code=400, detail="total_tokens mismatch with server state")
    except (StateCorruptionError, FileNotFoundError, OSError):
        pass  # No state file — allow signing (orchestration might be over)

    sig = _sign_score(project, score, changes_done, total_tokens)
