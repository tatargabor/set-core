"""Does the provider publish a model set-core does not know? — advice, never an edit.

Anthropic's public model overview lists the current models with no key needed.
This module reads it, compares it with the ids set-core SHIPS (`DEFAULT_MODEL_IDS`)
and with what this MACHINE declares (`providers.json`), and says what is missing.
It changes nothing: which short name resolves to which id is a reviewed set-core
commit, not something to derive from a web page.

Three verdicts, and the direction of the third is the reason this module exists
rather than a one-line grep:

- ``current``  — at least one upstream id was parsed, and every one is covered.
- ``behind``   — an upstream id set-core does not ship, or a shipped name the
                 machine's catalogue does not offer (B-159).
- ``unknown``  — the fetch failed, or the page yielded ZERO ids. Never
                 ``current``: a check that could not measure and one that found
                 nothing to report look identical from outside, and only one of
                 them is true.

⚠ Ids are taken ONLY from the overview table's "Claude API ID" and "Claude API
alias" rows. A page-wide ``claude-…`` match also collects link slugs such as
``claude-prompting-best-practices`` — prose read as fact.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .defaults import ANTHROPIC_MODEL_NAMES, DEFAULT_MODEL_IDS

logger = logging.getLogger(__name__)

PROVIDER = "anthropic"
SOURCE_URL = "https://platform.claude.com/docs/en/about-claude/models/overview.md"
CACHE_TTL_S = 24 * 3600
FETCH_TIMEOUT_S = 10

CURRENT, BEHIND, UNKNOWN = "current", "behind", "unknown"

_ID_ROW = "Claude API ID"
_ALIAS_ROW = "Claude API alias"
_BACKTICKED = re.compile(r"`([^`]+)`")
_FAMILY = re.compile(r"^claude-([a-z]+)-")

#: A fetcher returns the page text or raises. Injected so tests never touch the network.
Fetcher = Callable[[str], str]


def cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "set-core" / "upstream-models.json"


def parse_overview(text: str) -> List[Tuple[str, Optional[str]]]:
    """``[(api_id, alias_or_None), ...]`` by column, from the two anchored rows only.

    A row counts only when its FIRST cell is exactly the label — anchored on the
    whole cell, so a row that merely mentions "Claude API ID" in prose does not.
    """
    rows: Dict[str, List[str]] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] not in (_ID_ROW, _ALIAS_ROW):
            continue
        values = []
        for cell in cells[1:]:
            m = _BACKTICKED.search(cell)
            values.append(m.group(1).strip() if m else "")
        rows.setdefault(cells[0], values)
    ids = rows.get(_ID_ROW, [])
    aliases = rows.get(_ALIAS_ROW, [])
    out: List[Tuple[str, Optional[str]]] = []
    for i, api_id in enumerate(ids):
        if not api_id.startswith("claude-"):
            continue
        alias = aliases[i] if i < len(aliases) and aliases[i].startswith("claude-") else None
        out.append((api_id, alias))
    return out


def _default_fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "set-core upstream-model-watch"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:  # noqa: S310 — fixed https URL
        return resp.read().decode("utf-8", errors="replace")


def _read_cache(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("upstream models: unreadable cache %s: %s", path, exc)
        return None
    if not isinstance(data, dict) or not isinstance(data.get("models"), list) or not data["models"]:
        logger.warning("upstream models: cache %s has no models, ignoring it", path)
        return None
    return data


def _write_cache(path: Path, models: List[Tuple[str, Optional[str]]], fetched_at: float) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "source": SOURCE_URL, "fetched_at": fetched_at,
            "models": [{"id": i, "alias": a} for i, a in models],
        }, indent=2))
        os.replace(tmp, path)
        logger.debug("upstream models: cached %d ids at %s", len(models), path)
    except OSError as exc:
        logger.warning("upstream models: could not write cache %s: %s", path, exc)


def upstream_models(
    *, refresh: bool = False, fetch: Optional[Fetcher] = None,
    cache: Optional[Path] = None, now: Optional[float] = None,
) -> Tuple[Optional[List[Tuple[str, Optional[str]]]], Optional[float], Optional[str]]:
    """``(models, fetched_at, error)``. ``models`` is ``None`` when nothing was measured.

    A failed fetch returns the error and leaves a good cache untouched.
    """
    path = cache or cache_path()
    t = time.time() if now is None else now
    if not refresh:
        cached = _read_cache(path)
        if cached and t - float(cached.get("fetched_at", 0)) < CACHE_TTL_S:
            models = [(m["id"], m.get("alias")) for m in cached["models"] if m.get("id")]
            logger.debug("upstream models: cache hit (%d ids)", len(models))
            return models, float(cached["fetched_at"]), None

    try:
        text = (fetch or _default_fetch)(SOURCE_URL)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("upstream models: fetch %s failed: %s", SOURCE_URL, exc)
        return None, None, f"could not fetch {SOURCE_URL}: {exc}"
    models = parse_overview(text)
    if not models:
        logger.warning("upstream models: %s yielded no '%s' row — page shape changed?", SOURCE_URL, _ID_ROW)
        return None, None, f"no '{_ID_ROW}' row found on {SOURCE_URL} — the page may have changed shape"
    logger.info("upstream models: fetched %d ids from %s", len(models), SOURCE_URL)
    _write_cache(path, models, t)
    return models, t, None


@dataclass
class Report:
    verdict: str
    source: str = SOURCE_URL
    fetched_at: Optional[float] = None
    error: Optional[str] = None
    #: Upstream ids set-core ships no mapping for: {"id", "family", "shorthand_resolves_to"}.
    not_shipped: List[Dict[str, Optional[str]]] = field(default_factory=list)
    #: Shipped names the machine's anthropic catalogue does not offer.
    not_declared: List[str] = field(default_factory=list)
    machine_config: Optional[str] = None
    machine_note: Optional[str] = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _shipped_ids() -> set:
    return {v.split("[", 1)[0] for v in DEFAULT_MODEL_IDS.values()}


def _pass_through_families() -> set:
    """Shipped names delivered to the CLI untranslated (e.g. ``fable``)."""
    return {n for n in ANTHROPIC_MODEL_NAMES if n not in DEFAULT_MODEL_IDS and "-" not in n}


def not_shipped(models: List[Tuple[str, Optional[str]]]) -> List[Dict[str, Optional[str]]]:
    shipped, passthrough = _shipped_ids(), _pass_through_families()
    out = []
    for api_id, alias in models:
        if api_id in shipped or (alias and alias in shipped):
            continue
        m = _FAMILY.match(api_id)
        family = m.group(1) if m else None
        if family in passthrough:
            continue
        out.append({"id": api_id, "family": family,
                    "shorthand_resolves_to": DEFAULT_MODEL_IDS.get(family) if family else None})
    return out


def _machine_gap() -> Tuple[List[str], Optional[str], Optional[str]]:
    """``(missing_names, config_path, note)`` — read-only."""
    from .config import load_or_legacy, config_path
    from .errors import ProviderError
    try:
        cfg, _notice = load_or_legacy()
    except ProviderError as exc:
        return [], None, f"machine catalogue not checked: {exc}"
    declared = cfg.providers.get(PROVIDER)
    if declared is None:
        return [], str(config_path()), f"machine catalogue not checked: no '{PROVIDER}' provider declared"
    have = set(declared.models)
    return [n for n in ANTHROPIC_MODEL_NAMES if n not in have], str(config_path()), None


def check(*, refresh: bool = False, fetch: Optional[Fetcher] = None,
          cache: Optional[Path] = None, now: Optional[float] = None) -> Report:
    """The whole verdict. Writes nothing but its own cache file."""
    missing, cfg_path, note = _machine_gap()
    models, fetched_at, error = upstream_models(refresh=refresh, fetch=fetch, cache=cache, now=now)
    report = Report(verdict=UNKNOWN, fetched_at=fetched_at, error=error,
                    not_declared=missing, machine_config=cfg_path, machine_note=note)
    if models is None:
        # The machine gap is still reported, but the verdict stays unknown: the
        # upstream half was not measured, and `behind` would imply it had been.
        return report
    report.not_shipped = not_shipped(models)
    report.verdict = BEHIND if (report.not_shipped or missing) else CURRENT
    logger.info("upstream models: verdict=%s not_shipped=%s not_declared=%s", report.verdict,
                [x["id"] for x in report.not_shipped], missing)
    return report


def advice(report: Report) -> List[str]:
    """Human-readable lines for the CLI."""
    lines: List[str] = []
    age = ""
    if report.fetched_at:
        age = f" (list fetched {time.strftime('%Y-%m-%d %H:%M', time.localtime(report.fetched_at))})"
    if report.verdict == UNKNOWN:
        lines.append(f"unknown — {report.error}")
    elif report.verdict == CURRENT:
        lines.append(f"current — set-core ships every model Anthropic lists{age}")
    else:
        lines.append(f"behind{age}")
    for x in report.not_shipped:
        via = (f"; `{x['family']}` currently resolves to {x['shorthand_resolves_to']}"
               if x.get("shorthand_resolves_to") else "")
        lines.append(f"  Anthropic lists {x['id']}, which set-core does not ship{via}")
    if report.not_shipped:
        lines.append("  → update set-core: add the name and id to lib/set_orch/providers/defaults.py "
                     "and bin/set-common.sh (decide whether the shorthand moves)")
    if report.not_declared:
        lines.append(f"  set-core ships {', '.join(report.not_declared)}, but this machine's "
                     f"'{PROVIDER}' catalogue does not offer them")
        lines.append(f"  → add them to providers.{PROVIDER}.models in {report.machine_config}")
    if report.machine_note:
        lines.append(f"  {report.machine_note}")
    return lines
