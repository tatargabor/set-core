"""The probe contract and the finding a probe returns.

A probe is a deterministic measurement: it costs no tokens, so a tick can run it every few
minutes. What it returns is SHAPE ONLY — counts, durations, timestamps, ids, unit names and
project slugs. Never transcript text, never a message body, never file content: the finding
store and the triage prompt are built from these fields and nothing else (design D7).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

SEVERITIES = ("fail", "warn")
PROBE_ERROR = "watchdog-probe-error"

#: Evidence values a finding may carry. Anything else is rejected at construction, so a
#: probe cannot smuggle a text blob into the store or the prompt by accident.
EVIDENCE_TYPES = (int, float, bool, type(None))
EVIDENCE_STR_MAX = 120


def fingerprint(probe: str, subject: str) -> str:
    """One anomaly = one finding: the identity is the probe and the subject, nothing else."""
    return hashlib.sha256(f"{probe}\0{subject}".encode("utf-8")).hexdigest()[:16]


def _check_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for key, value in evidence.items():
        if isinstance(value, EVIDENCE_TYPES):
            clean[key] = value
        elif isinstance(value, str) and len(value) <= EVIDENCE_STR_MAX and "\n" not in value:
            clean[key] = value
        elif isinstance(value, (list, tuple)) and all(
                isinstance(v, EVIDENCE_TYPES) or (isinstance(v, str) and len(v) <= EVIDENCE_STR_MAX)
                for v in value) and len(value) <= 20:
            clean[key] = list(value)
        else:
            raise ValueError(f"evidence field {key!r} is not shape-only")
    return clean


@dataclass
class Finding:
    probe: str
    severity: str
    subject: str
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    #: The project the probe believes owns the defect, when it knows (triage may override).
    owner_hint: Optional[str] = None

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity {self.severity!r} not in {SEVERITIES}")
        if "\n" in self.summary or len(self.summary) > 200:
            raise ValueError("summary must be one line of at most 200 characters")
        self.evidence = _check_evidence(self.evidence)

    @property
    def fp(self) -> str:
        return fingerprint(self.probe, self.subject)


@dataclass
class Context:
    """What a probe may read: a clock and the shared fetches a tick does once."""
    now: float
    get: Callable[..., Any]
    cache: Dict[str, Any] = field(default_factory=dict)
    #: Per-probe memory across ticks (shape-only, persisted in the store).
    states: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def state(self, probe: str) -> Dict[str, Any]:
        return self.states.setdefault(probe, {})

    def once(self, key: str, fetch: Callable[[], Any]) -> Any:
        """Fetch a shared input (the fleet payload) once per tick, failures included."""
        if key not in self.cache:
            try:
                self.cache[key] = (True, fetch())
            except Exception as exc:  # noqa: BLE001 — the probe reports it as could-not-measure
                logger.warning("watchdog: shared input %s unreadable: %s", key, type(exc).__name__)
                self.cache[key] = (False, type(exc).__name__)
        return self.cache[key]


@dataclass
class Probe:
    name: str
    interval_s: int
    collect: Callable[[Context], List[Finding]]
    description: str = ""

    def interval(self, get: Callable[..., Any]) -> int:
        raw = get(f"watchdog.probe.{self.name}.interval_s")
        try:
            return max(60, int(raw)) if raw is not None else self.interval_s
        except (TypeError, ValueError):
            logger.warning("watchdog: bad interval %r for probe %s; using %s", raw, self.name, self.interval_s)
            return self.interval_s


_REGISTRY: Dict[str, Probe] = {}


def register(probe: Probe) -> Probe:
    _REGISTRY[probe.name] = probe
    return probe


def registry() -> Dict[str, Probe]:
    from . import probes  # noqa: F401 — importing registers the built-ins
    return dict(_REGISTRY)
