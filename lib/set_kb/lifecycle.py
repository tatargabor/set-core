"""The index lifecycle of one project: resolve, guard, lock, refresh, search.

The contract this module exists for (design D6/D7, and the requirements they
carry): every search first brings the index up to date — an unchanged file
skipped by mtime+size, a changed file re-chunked, a deleted file removed, a
stale schema/SQLite/corpus-config stamp rebuilt — and when TWO agents search
at once, ONE of them refreshes and the other searches the current snapshot
and SAYS SO on the page. Neither fails.

Concurrency is one advisory writer lock (`.set/kb/index.lock`,
`fcntl.flock`): available on macOS and Linux, released by the kernel when the
holder dies, so there is no staleness to clean up. WAL mode (already set by
the store) lets readers proceed during a refresh; the store's busy timeout
covers the commit window.

`--no-reindex` skips the refresh entirely for measurement runs: it queries
the existing index and does not modify it.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from set_kb.config import (
    KbConfig,
    corpus_config_hash,
    footer_exclusions,
    index_options,
    load_config,
    read_framework_ledger,
    search_options,
)
from set_kb.indexer import AtomicIndexSource, RunIndexAtomicOpts, run_index_atomic
from set_kb.project import ProjectError, ensure_ignored, index_paths, resolve_root, seed_from_main
from set_kb.runtime import ensure_runtime
from set_kb.search import search_page
from set_kb.store import SqliteFtsStore
from set_kb.types import SearchPage

logger = logging.getLogger(__name__)


class RefreshLock:
    """The one-writer lock over `.set/kb/index.lock`. Non-blocking on purpose:
    a search that would wait is a search that should serve the snapshot
    instead (AC: two agents search at once — neither fails, neither waits)."""

    def __init__(self, path: str):
        self.path = path
        self._fd: Optional[int] = None

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o644)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            os.close(self._fd)
            self._fd = None
            return False

    def release(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None

    def __enter__(self) -> "RefreshLock":
        self.acquired = self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


@dataclass
class Project:
    """Everything one invocation needs about the project it serves."""

    root: str
    config: KbConfig
    db_path: str
    lock_path: str
    framework_ledger: Optional[dict] = None
    seeded: bool = False  # this run copied the main checkout's index


@dataclass
class RefreshResult:
    """What the refresh phase did — or deliberately did not."""

    refreshed: bool = False  # this caller ran a refresh
    snapshot: bool = False  # the lock was held elsewhere; nothing was refreshed
    no_reindex: bool = False  # the caller asked to skip the refresh
    seeded: bool = False  # the index was copied from the main checkout first
    stats: Optional[dict] = None
    notes: list = field(default_factory=list)


def load_project(start_dir, machine_path=None) -> Project:
    """Resolve the project for `start_dir` (git root), load and validate its
    config, and carry the paths + ledger the lifecycle acts on. The FTS5 probe
    runs FIRST so a runtime without FTS5 fails before anything is created
    (AC: a failing probe creates no index)."""
    ensure_runtime()
    root = resolve_root(start_dir)
    cfg = load_config(root, machine_path=machine_path)
    db_path, lock_path = index_paths(root)
    return Project(
        root=root,
        config=cfg,
        db_path=db_path,
        lock_path=lock_path,
        framework_ledger=read_framework_ledger(root),
    )


def refresh(project: Project, force: bool = False, no_reindex: bool = False) -> RefreshResult:
    """Bring the index up to date — or report why this caller did not.

    The ignore guard runs before the lock: creating `.set/kb/index.lock` is
    already a write under `.set/`, and the guard is the one place the
    "never in git" promise can still be cheaply kept.
    """
    if no_reindex:
        result = RefreshResult(no_reindex=True)
        result.notes.append("index not refreshed (--no-reindex): results come from the index as it stands")
        return result

    ensure_ignored(project.root, project.db_path)
    with RefreshLock(project.lock_path) as lock:
        if not lock.acquired:
            logger.info("kb index: a concurrent refresh holds the lock — searching the current snapshot")
            result = RefreshResult(snapshot=True)
            result.notes.append(
                "index not refreshed: a concurrent refresh holds the lock — results are from the current snapshot"
            )
            return result
        project.seeded = seed_from_main(project.root, project.db_path)
        sources = [AtomicIndexSource(id=s.ref, dir=os.path.join(project.root, s.ref)) for s in project.config.sources]
        opts = index_options(project.config, framework_ledger=project.framework_ledger)
        if force:
            opts.force = True
        stats = run_index_atomic(
            RunIndexAtomicOpts(
                db_path=project.db_path,
                sources=sources,
                index_opts=opts,
                stored_row_config_hash=corpus_config_hash(project.config),
            )
        )
        return RefreshResult(refreshed=True, seeded=project.seeded, stats=stats)


@dataclass
class ProjectSearch:
    """One search over one project: the page PLUS the facts the footer and
    the JSON contract carry about how it was produced."""

    page: SearchPage
    root: str
    refreshed: bool
    snapshot: bool
    no_reindex: bool
    notes: list
    linked: list = field(default_factory=list)  # LinkedSearch, one per configured link

    @property
    def hits(self):
        return self.page.hits

    def to_json_dict(self) -> dict:
        out = self.page.to_json_dict()
        out["root"] = self.root
        out["refreshed"] = self.refreshed
        out["notes"] = list(self.notes)
        return out


@dataclass
class LinkedSearch:
    """One linked project's own page, or why it has none. A link that could not
    be searched carries `error` and is SHOWN — a silently skipped link would read
    as "the linked corpus has nothing on this"."""

    project: str
    scope: Optional[str] = None
    about: Optional[str] = None
    search: Optional["ProjectSearch"] = None
    error: Optional[str] = None


def registry_path() -> str:
    """The set-core project registry: SET_CORE_REGISTRY, else SET_CONFIG_DIR,
    else the XDG config dir — the same resolution the shell tools use."""
    env = os.environ.get("SET_CORE_REGISTRY", "").strip()
    if env:
        return os.path.expanduser(env)
    cfg_dir = os.environ.get("SET_CONFIG_DIR", "").strip()
    if not cfg_dir:
        cfg_dir = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "set-core")
    return os.path.join(cfg_dir, "projects.json")


def registry_project_root(name: str) -> str:
    """A registered project's path, or ProjectError naming what is missing."""
    path = registry_path()
    try:
        with open(path, encoding="utf-8") as f:
            reg = json.load(f)
    except FileNotFoundError:
        raise ProjectError(f"no project registry at {path}") from None
    except (OSError, ValueError) as e:
        raise ProjectError(f"project registry {path} is unreadable: {e}") from None
    entry = (reg.get("projects") or {}).get(name) if isinstance(reg, dict) else None
    if not isinstance(entry, dict) or not entry.get("path"):
        raise ProjectError(f"project {name!r} is not in the registry ({path})")
    root = os.path.expanduser(str(entry["path"]))
    if not os.path.isdir(root):
        raise ProjectError(f"project {name!r} is registered at {root}, which does not exist")
    return root


def search_project(
    project: Project,
    query: str,
    limit: int = 10,
    root: Optional[str] = None,
    channel: Optional[str] = None,
    scope: Optional[str] = None,
    exclude_paths: tuple = (),
    lane: bool = True,
    no_reindex: bool = False,
    force: bool = False,
) -> ProjectSearch:
    """Refresh (unless prevented) and search — the whole engine in one call,
    and the exact behavior every surface (CLI, MCP) shares."""
    rr = refresh(project, force=force, no_reindex=no_reindex)

    if not os.path.exists(project.db_path):
        # An empty corpus (nothing to index yet) or a first build that found
        # nothing — an honest empty page, not an error.
        page = SearchPage(hits=[], total=0, has_more=False, exclusions=footer_exclusions(project.config))
        notes = list(rr.notes)
        notes.append("no index exists yet — nothing has been indexed in this project")
        return ProjectSearch(page=page, root=project.root, refreshed=False, snapshot=False, no_reindex=True, notes=notes)

    store = SqliteFtsStore(project.db_path)
    store.init()
    try:
        overrides: dict = {"limit": limit, "exclude_paths": list(exclude_paths)}
        if root is not None:
            overrides["root"] = root
        if channel is not None:
            overrides["channel"] = channel
        if scope is not None:
            overrides["scope"] = scope
        if not lane:
            # AC: lane disabled for measurement — no query in the run may use it.
            overrides["lane_quota"] = 0
            overrides["lane_channels"] = ()
        opts = search_options(project.config, **overrides)
        page = search_page(store, query, opts, exclusions=footer_exclusions(project.config))
    finally:
        store.close()
    return ProjectSearch(
        page=page,
        root=project.root,
        refreshed=rr.refreshed,
        snapshot=rr.snapshot,
        no_reindex=rr.no_reindex,
        notes=list(rr.notes),
    )


def linked_project(project: Project, name: str) -> Project:
    """A project this one links to, loaded with ITS OWN configuration. Only a
    name listed in `linked` resolves — the link is the permission."""
    if name not in {ln.project for ln in project.config.linked}:
        raise ProjectError(f"{name!r} is not a linked project of {project.root} (config.linked)")
    root = registry_project_root(name)
    if os.path.realpath(root) == os.path.realpath(project.root):
        raise ProjectError(f"{name!r} is this project itself")
    return load_project(root)


def search_linked(project: Project, query: str, limit: int = 10, lane: bool = True, no_reindex: bool = False) -> list:
    """Search every linked project's own index with its own configuration, the
    link's scope applied. One level only: a linked project's own links are not
    followed. Every failure becomes a `LinkedSearch.error`, never an exception —
    the caller's own page must still come back."""
    out: list = []
    for ln in project.config.linked:
        item = LinkedSearch(project=ln.project, scope=ln.scope, about=ln.about)
        try:
            lp = linked_project(project, ln.project)
            item.search = search_project(lp, query, limit=limit, scope=ln.scope, lane=lane, no_reindex=no_reindex)
            logger.info("kb linked: %s searched (%d hits)", ln.project, len(item.search.hits))
        except Exception as e:  # noqa: BLE001 — a link's failure is reported on the page
            item.error = f"{type(e).__name__}: {e}" if not isinstance(e, ProjectError) else str(e)
            logger.warning("kb linked: %s not searched: %s", ln.project, item.error)
        out.append(item)
    return out


__all__ = [
    "LinkedSearch", "Project", "ProjectSearch", "ProjectError", "RefreshLock", "RefreshResult",
    "linked_project", "load_project", "refresh", "registry_path", "registry_project_root",
    "search_linked", "search_project",
]
