"""A project's own local pages — declared, listed, and checked for being up.

A project often has a small web page of its own that the owner uses by hand: a reply queue, a
preview server, an admin console on localhost. Nothing in the framework knew about any of them, so
the only way back to one was to remember its port. This module lets a project DECLARE its pages,
and the Now card lists them with an up/down marker.

Two places a page can be declared, and both are read:

* the project's own `.set-endpoint.json`, a `pages` list — the long-term home, versioned with the
  project, readable WITHOUT a status contract (a project may have pages and no commands);
* set-core's machine-local config for that project (`set-config set pages '<json>' --project P`)
  — for a page whose project has no manifest yet, or a port that only this machine uses. A local
  entry with the same name replaces the manifest's.

A page is `{ "name": str, "url": "http(s)://…", "description"?: str }`. Anything else is skipped
and counted, never guessed at.

The check is a GET with a short timeout: any HTTP answer below 500 is "up", a refused or timed-out
connection is "down", and the error CLASS is kept (never the body). Results are cached briefly so
a polling card does not hammer a page.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import local_config
from ..project_status import MANIFEST_FILENAME

logger = logging.getLogger(__name__)

PAGES_KEY = "pages"
PROBE_TIMEOUT_S = 2.0
PROBE_CACHE_S = 30.0
MAX_PAGES_PER_PROJECT = 12

_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


@dataclass
class Page:
    project: str
    name: str
    url: str
    source: str                      # "manifest" or "local"
    description: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        out = {"project": self.project, "name": self.name, "url": self.url, "source": self.source}
        if self.description:
            out["description"] = self.description
        return out


def _valid(raw: Any) -> Optional[Dict[str, str]]:
    """One declared page, or None when it is not usable."""
    if not isinstance(raw, dict):
        return None
    name = raw.get("name")
    url = raw.get("url")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
        return None
    if not isinstance(url, str) or not url.strip().lower().startswith(("http://", "https://")):
        return None
    out = {"name": name.strip(), "url": url.strip()}
    desc = raw.get("description")
    if isinstance(desc, str) and desc.strip():
        out["description"] = desc.strip()[:160]
    return out


def _from_manifest(project_path: str) -> Tuple[List[Dict[str, str]], int]:
    path = Path(project_path) / MANIFEST_FILENAME
    if not path.is_file():
        return [], 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("project_pages: unreadable %s in %s (%s)", MANIFEST_FILENAME,
                       project_path, type(exc).__name__)
        return [], 0
    items = raw.get(PAGES_KEY) if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return [], 0
    good = [p for p in (_valid(x) for x in items) if p]
    return good, len(items) - len(good)


def _from_local(project: str) -> Tuple[List[Dict[str, str]], int]:
    value = local_config.get(PAGES_KEY, project=project)
    if value is None:
        return [], 0
    if isinstance(value, str):
        # The env and the CLI hand a value over as text.
        try:
            value = json.loads(value)
        except ValueError:
            logger.warning("project_pages: local '%s' for %s is not JSON — ignored", PAGES_KEY, project)
            return [], 1
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return [], 1
    good = [p for p in (_valid(x) for x in value) if p]
    return good, len(value) - len(good)


def declared_pages(projects: List[Dict[str, Any]]) -> Tuple[List[Page], int]:
    """Every declared page of every registered project, and how many entries were malformed."""
    pages: List[Page] = []
    malformed = 0
    for p in projects:
        name, path = p.get("name"), p.get("path")
        if not name or not path:
            continue
        man, bad_m = _from_manifest(str(path))
        loc, bad_l = _from_local(str(name))
        malformed += bad_m + bad_l
        by_name: Dict[str, Page] = {}
        for x in man:
            by_name[x["name"]] = Page(name, x["name"], x["url"], "manifest", x.get("description"))
        for x in loc:   # a local entry with the same name replaces the manifest's
            by_name[x["name"]] = Page(name, x["name"], x["url"], "local", x.get("description"))
        pages.extend(list(by_name.values())[:MAX_PAGES_PER_PROJECT])
    if malformed:
        logger.warning("project_pages: %d declared page(s) skipped as malformed", malformed)
    return pages, malformed


def probe(url: str, *, now: Optional[float] = None, timeout: float = PROBE_TIMEOUT_S) -> Dict[str, Any]:
    """Is the page answering? Cached for PROBE_CACHE_S. Keeps the status and an error class only."""
    now = time.time() if now is None else now
    with _CACHE_LOCK:
        hit = _CACHE.get(url)
        if hit and now - hit[0] < PROBE_CACHE_S:
            return hit[1]
    result: Dict[str, Any]
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "set-core-pages/1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — declared http(s) only
            result = {"up": resp.status < 500, "status": resp.status, "error": None}
    except urllib.error.HTTPError as exc:
        result = {"up": exc.code < 500, "status": exc.code, "error": None if exc.code < 500 else "HTTPError"}
    except Exception as exc:   # refused, timed out, DNS — the class is the useful part
        result = {"up": False, "status": None, "error": type(exc).__name__}
    result["checkedAt"] = now
    with _CACHE_LOCK:
        _CACHE[url] = (now, result)
    logger.debug("project_pages: probe %s -> up=%s status=%s error=%s",
                 url.split("?")[0], result["up"], result["status"], result["error"])
    return result


def pages_with_state(projects: List[Dict[str, Any]], *, now: Optional[float] = None) -> Dict[str, Any]:
    """The answer of GET /api/fleet/pages: each page with its up/down state, probed in parallel."""
    now = time.time() if now is None else now
    pages, malformed = declared_pages(projects)
    out: List[Dict[str, Any]] = []
    if pages:
        with ThreadPoolExecutor(max_workers=min(8, len(pages))) as pool:
            states = list(pool.map(lambda pg: probe(pg.url, now=now), pages))
        for pg, st in zip(pages, states):
            out.append({**pg.as_dict(), "up": st["up"], "status": st["status"], "error": st["error"]})
    return {"pages": out, "down": sum(1 for p in out if not p["up"]), "malformed": malformed}


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
