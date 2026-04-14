"""Persist a gate's verdict next to its Claude session JSONL.

Background
----------
Gate verdicts (review pass/fail, spec_verify pass/fail, etc.) are decided
by the orchestrator from the Claude session output — historically through
a regex fast-path with a Sonnet `classify_verdict` fallback. Until now,
the web dashboard's session listing rendered an INDEPENDENT outcome
("success" / "error") by keyword-scanning the assistant's last message
("review fail", "[critical]", "fixed", "committed", ...). The two paths
disagreed regularly: the gate would pass a change because the classifier
found 0 critical findings, but the session card would show "failed"
because the prose mentioned `[CRITICAL]` while quoting prior findings.

This module provides a single-source-of-truth alternative: the gate that
decides the verdict ALSO writes a `<session_id>.verdict.json` sidecar
next to the Claude session JSONL. The sessions API reads the sidecar
verbatim — no second LLM call, no second-guess heuristic.

How callers use it
------------------
1. Just before invoking `run_claude_logged` for a gate, capture a baseline:

       baseline = snapshot_session_files(wt_path)

2. Just after the gate decides its verdict, persist:

       persist_gate_verdict(
           cwd=wt_path,
           baseline=baseline,
           change_name="my-change",
           gate="review",
           verdict="pass",
           critical_count=0,
           source="classifier_confirmed",
           summary="0 critical findings (classifier verified fast-path miss)",
       )

`persist_gate_verdict` finds the JSONL Claude just created and writes a
sidecar JSON file next to it. Subsequent gate runs (retries) get their
own session and their own sidecar, so retry granularity is preserved.

The disambiguation marker is the `[PURPOSE:<gate>:<change>]` tag that
`run_claude_logged` already prepends to every prompt — so we can pick
the right session out even when multiple Claude calls land in the same
project dir between snapshot and post-call.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


def _claude_mangle(path: str) -> str:
    """Mangle a filesystem path the way Claude CLI does for ~/.claude/projects/.

    Mirrors `lib/set_orch/api/helpers.py::_claude_mangle`. Inlined here so
    the core gate code does not import from the API layer.
    """
    return path.lstrip("/").replace("/", "-").replace(".", "-").replace("_", "-")


def claude_session_dir(cwd: str | Path) -> Path:
    """Return the Claude projects dir for a given cwd.

    The directory may not exist yet — Claude CLI creates it on the first
    session. Callers must not assume `is_dir()`.
    """
    return Path.home() / ".claude" / "projects" / f"-{_claude_mangle(str(cwd))}"


def snapshot_session_files(cwd: str | Path) -> set[str]:
    """Snapshot the JSONL session-file stems currently in the cwd's session dir.

    Used as a baseline immediately before a gate's `run_claude_logged`
    call. The post-call diff (`find_new_session_file`) uses this to pick
    out the file Claude CLI just created.
    """
    d = claude_session_dir(cwd)
    if not d.is_dir():
        return set()
    try:
        return {f.stem for f in d.iterdir() if f.is_file() and f.suffix == ".jsonl"}
    except OSError as exc:
        logger.warning("snapshot_session_files: cannot list %s: %s", d, exc)
        return set()


def find_new_session_file(
    cwd: str | Path,
    baseline: set[str],
    purpose_marker: str = "",
) -> Path | None:
    """Find the JSONL that appeared since `baseline` was captured.

    If `purpose_marker` is provided (e.g. `"[PURPOSE:review:my-change]"`),
    the picked session must contain that exact marker in its first 4 KB —
    this disambiguates concurrent Claude calls writing into the same dir.
    Without a marker, the most recently mtime'd new file wins.
    """
    d = claude_session_dir(cwd)
    if not d.is_dir():
        return None
    candidates: list[tuple[float, Path]] = []
    try:
        for f in d.iterdir():
            if not f.is_file() or f.suffix != ".jsonl":
                continue
            if f.stem in baseline:
                continue
            try:
                st = f.stat()
            except OSError:
                continue
            candidates.append((st.st_mtime, f))
    except OSError as exc:
        logger.warning("find_new_session_file: cannot list %s: %s", d, exc)
        return None
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    if not purpose_marker:
        return candidates[0][1]
    marker_bytes = purpose_marker.encode("utf-8")
    for _, path in candidates:
        try:
            with open(path, "rb") as fh:
                head = fh.read(4096)
        except OSError:
            continue
        if marker_bytes in head:
            return path
    return None


@dataclass
class GateVerdict:
    """Schema written to `<session_id>.verdict.json` next to a session JSONL.

    Single source of truth for the gate's decision on this exact session.
    The web dashboard reads this directly so the UI matches the gate.
    """
    gate: str                # "review" / "spec_verify" / "test_fix" / ...
    verdict: str             # "pass" or "fail"
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    source: str = ""         # fast_path | classifier_confirmed | classifier_override | classifier_downgrade | classifier_failed
    change: str = ""
    summary: str = ""        # one-line description of why we landed here
    # Severity downgrade audit trail — populated when the classifier lowers
    # a reviewer-tagged severity per the rubric. Each entry: {from, to, summary}.
    downgrades: list = None
    # Structured findings extracted from the gate output. When non-empty, the
    # retry_context builder renders FILE/LINE/FIX blocks verbatim instead of
    # the 1-line summary. Forward-compat: legacy sidecars without this field
    # still parse cleanly and fall back to `summary` — see
    # `read_verdict_sidecar` and `engine._build_reset_retry_context`.
    findings: list = None

    def __post_init__(self) -> None:
        if self.downgrades is None:
            self.downgrades = []
        if self.findings is None:
            self.findings = []

    def to_outcome(self) -> str:
        """Translate to the {success, error, unknown} the session API uses."""
        if self.verdict == "pass":
            return "success"
        if self.verdict == "fail":
            return "error"
        return "unknown"


def _sidecar_path(session_path: Path) -> Path:
    return session_path.with_name(f"{session_path.stem}.verdict.json")


def write_verdict_sidecar(session_path: Path, verdict: GateVerdict) -> None:
    """Atomically write the sidecar JSON next to a session JSONL."""
    sidecar = _sidecar_path(session_path)
    tmp = sidecar.with_suffix(sidecar.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(asdict(verdict), indent=2))
        tmp.rename(sidecar)
        logger.info(
            "Gate verdict sidecar written: %s gate=%s verdict=%s critical=%d source=%s",
            sidecar.name, verdict.gate, verdict.verdict,
            verdict.critical_count, verdict.source,
        )
    except OSError as exc:
        logger.warning("Could not write verdict sidecar %s: %s", sidecar, exc)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def read_verdict_sidecar(session_path: Path) -> GateVerdict | None:
    """Read a previously-written sidecar. Returns None if missing or corrupt."""
    sidecar = _sidecar_path(session_path)
    if not sidecar.is_file():
        return None
    try:
        data = json.loads(sidecar.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read verdict sidecar %s: %s", sidecar, exc)
        return None
    known = {
        "gate", "verdict", "critical_count", "high_count", "medium_count",
        "low_count", "source", "change", "summary", "downgrades", "findings",
    }
    clean = {k: v for k, v in data.items() if k in known}
    try:
        return GateVerdict(**clean)
    except TypeError as exc:
        logger.warning("Sidecar %s has invalid shape: %s", sidecar, exc)
        return None


def persist_gate_verdict(
    *,
    cwd: str | Path,
    baseline: set[str],
    change_name: str,
    gate: str,
    verdict: str,
    critical_count: int = 0,
    high_count: int = 0,
    medium_count: int = 0,
    low_count: int = 0,
    source: str = "",
    summary: str = "",
    downgrades: list | None = None,
    findings: list | None = None,
) -> Path | None:
    """Resolve the new session for the call we just made and write its sidecar.

    Returns the session JSONL path on success, or None if no new session
    was found (e.g. the Claude call failed before creating its file).
    The new-session lookup is keyed by the `[PURPOSE:<gate>:<change>]`
    marker so concurrent gate calls don't cross-write each other's sidecars.
    """
    marker = f"[PURPOSE:{gate}:{change_name}]"
    session = find_new_session_file(cwd, baseline, purpose_marker=marker)
    if session is None:
        logger.warning(
            "persist_gate_verdict: no new session in %s for %s — sidecar skipped",
            claude_session_dir(cwd), marker,
        )
        return None
    _normalized_findings: list = []
    for f in (findings or []):
        if isinstance(f, dict):
            _normalized_findings.append(f)
        elif hasattr(f, "to_dict"):
            _normalized_findings.append(f.to_dict())
        else:
            # Unknown shape — skip rather than crash the sidecar write.
            logger.debug("persist_gate_verdict: ignoring finding of type %s", type(f))
    write_verdict_sidecar(session, GateVerdict(
        gate=gate,
        verdict=verdict,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        source=source,
        change=change_name,
        summary=summary,
        downgrades=list(downgrades or []),
        findings=_normalized_findings,
    ))
    return session
