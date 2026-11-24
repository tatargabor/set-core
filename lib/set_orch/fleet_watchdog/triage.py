"""GLM triage of the findings a tick opened — one bounded call, shape-only input (D4, D7).

What goes into the prompt is exactly: each new finding's probe, severity, subject, summary
and evidence (all shape-only by construction, see `probe.py`), and the TITLES of the open
bug-register entries of set-core and of each finding's hinted owner. No transcript text, no
message body, no file content. A failure of any kind leaves the finding `untriaged` — the
fail direction of a bad answer is "shown", never "dismissed as noise".
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .. import local_config
from .store import Store

logger = logging.getLogger(__name__)

KEY_DAILY = "watchdog.triage_daily_calls"
KEY_MAX_CHARS = "watchdog.triage_max_chars"
DEFAULT_DAILY = 60
DEFAULT_MAX_CHARS = 8000
TIMEOUT_S = 300  # measured 2026-11-24: one 6-finding call answered in 121 s
BRIEF_MAX = 600
COUNTER = "triage_calls"
VERDICTS = ("real", "noise")
GUARD_ENV = "SET_WATCHDOG_TRIAGE"

#: The fields of a finding that may reach the model — and nothing else (tested).
PROMPT_FIELDS = ("fp", "probe", "severity", "subject", "summary", "evidence", "owner_hint")

PROMPT = """You triage anomalies that an automatic watchdog found on a developer machine that runs
many AI coding-agent sessions coordinated by a framework (set-core) and its tools
(set-agent-comm = the agent message bus, set-claude-handoff = the auto-clear/handoff watcher).

For EACH finding decide:
- verdict: "real" (a defect worth fixing), "noise" (expected behaviour or a measurement artefact),
  or "known:<id>" when one of the open bug-register titles below already describes it;
- owner: the project whose code must change (one of the registered project names below, most often
  set-core, set-agent-comm or set-claude-handoff);
- brief: at most 600 characters for the agent who will fix it: what is wrong, how to reproduce or
  measure it, and what would prove it fixed. Do not invent facts beyond the evidence.

Answer with ONLY a JSON object: {"findings": [{"fp": "...", "verdict": "...", "owner": "...", "brief": "..."}]}

REGISTERED PROJECTS: %(projects)s

OPEN BUG-REGISTER TITLES:
%(titles)s

FINDINGS:
%(findings)s
"""

Runner = Callable[[str], Optional[str]]


def register_titles(tree: str, limit: int = 60) -> List[str]:
    """`B-<n> — <title>` lines of the open section of a tree's bug register."""
    path = Path(tree) / "openspec" / "bugs" / "README.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    m = re.search(r"^## Open\s*$(.*?)(^## Closed\s*$|\Z)", text, flags=re.M | re.S)
    body = m.group(1) if m else ""
    out = []
    for line in body.splitlines():
        h = re.match(r"^### (B-\d+) — (.+)$", line)
        if h:
            out.append(f"{h.group(1)} — {h.group(2)[:160]}")
            if len(out) >= limit:
                break
    return out


def _registry() -> Dict[str, Any]:
    from .probes import _registry as reg
    return reg(None)


def run_glm(prompt: str, timeout: float = TIMEOUT_S) -> Optional[str]:
    exe = shutil.which("set-glm")
    if not exe:
        logger.warning("watchdog triage: no set-glm on PATH; findings stay untriaged")
        return None
    cmd = [exe, "-p", "--output-format", "json", "--settings", json.dumps({"disableAllHooks": True}),
           "--no-session-persistence"]
    t0 = time.monotonic()
    try:
        res = subprocess.run(cmd, input=prompt, text=True, capture_output=True, timeout=timeout,
                             cwd="/", env={**os.environ, GUARD_ENV: "1"})
    except subprocess.TimeoutExpired:
        logger.warning("watchdog triage: set-glm timed out after %ss", timeout)
        return None
    except OSError as exc:
        logger.warning("watchdog triage: set-glm could not start (%s)", type(exc).__name__)
        return None
    took = time.monotonic() - t0
    if res.returncode != 0:
        logger.warning("watchdog triage: set-glm exited %s after %.1fs", res.returncode, took)
        return None
    logger.info("watchdog triage: set-glm answered in %.1fs (%d chars)", took, len(res.stdout))
    try:
        outer = json.loads(res.stdout)
        return str(outer.get("result") or "") if isinstance(outer, dict) else None
    except ValueError:
        return res.stdout


def parse_answer(text: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return {}
    out = {}
    for item in (data.get("findings") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict) or not item.get("fp"):
            continue
        verdict = str(item.get("verdict") or "").strip()
        if verdict not in VERDICTS and not re.fullmatch(r"known:B-\d+", verdict):
            continue
        out[str(item["fp"])] = {"verdict": verdict, "owner": str(item.get("owner") or "")[:80] or None,
                                "brief": " ".join(str(item.get("brief") or "").split())[:BRIEF_MAX]}
    return out


def build_prompt(recs: List[Dict[str, Any]], max_chars: int, registry: Dict[str, Any]) -> Optional[str]:
    trees = {"set-core": str(Path(__file__).resolve().parents[3])}
    for rec in recs:
        hint = rec.get("owner_hint")
        entry = registry.get(hint) if hint else None
        if isinstance(entry, dict) and entry.get("path"):
            trees[hint] = os.path.expanduser(entry["path"])
    titles = []
    for name, tree in trees.items():
        titles += [f"[{name}] {t}" for t in register_titles(tree)]
    projects = ", ".join(sorted(n for n, e in registry.items() if isinstance(e, dict) and not e.get("archived")))
    findings = [{k: rec.get(k) for k in PROMPT_FIELDS} for rec in recs]
    prompt = PROMPT % {"projects": projects[:1500], "titles": "\n".join(titles) or "(none)",
                       "findings": json.dumps(findings, ensure_ascii=False, indent=1)}
    while len(prompt) > max_chars and titles:
        titles = titles[: len(titles) // 2]
        prompt = PROMPT % {"projects": projects[:1500], "titles": "\n".join(titles) or "(none)",
                           "findings": json.dumps(findings, ensure_ascii=False, indent=1)}
    return prompt if len(prompt) <= max_chars else None


def triage_new(store: Store, fps: List[str], *, now: float, get=local_config.get,
               runner: Optional[Runner] = None, registry: Optional[Dict[str, Any]] = None) -> int:
    """Triage the opened fingerprints in one call. Returns how many got a verdict."""
    recs = [store.findings[fp] for fp in fps if fp in store.findings and not store.is_muted(store.findings[fp], now)]
    if not recs:
        return 0
    try:
        daily = int(get(KEY_DAILY, default=DEFAULT_DAILY))
        max_chars = int(get(KEY_MAX_CHARS, default=DEFAULT_MAX_CHARS))
    except (TypeError, ValueError):
        daily, max_chars = DEFAULT_DAILY, DEFAULT_MAX_CHARS
    if store.counter(COUNTER, now) >= daily:
        logger.info("watchdog triage: daily cap %d reached; %d finding(s) stay untriaged", daily, len(recs))
        return 0
    prompt = None
    while recs:
        prompt = build_prompt(recs, max_chars, _registry() if registry is None else registry)
        if prompt:
            break
        recs = recs[:-1]                   # too large even without titles: triage fewer this tick
    if not prompt:
        logger.warning("watchdog triage: one finding alone exceeds %d chars; left untriaged", max_chars)
        return 0
    store.bump(COUNTER, now)
    answer = parse_answer((runner or run_glm)(prompt))
    done = 0
    for rec in recs:
        verdict = answer.get(rec["fp"])
        if not verdict:
            continue
        rec["triage"] = {**verdict, "at": now}
        done += 1
        logger.info("watchdog triage: %s %s -> %s (owner %s)", rec.get("probe"), rec["fp"],
                    verdict["verdict"], verdict.get("owner"))
    if done < len(recs):
        logger.warning("watchdog triage: %d of %d finding(s) got no usable verdict; untriaged",
                       len(recs) - done, len(recs))
    return done
