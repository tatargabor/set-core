"""Findability: the deterministic acceptance test for a project's corpus.

A saved recording is only as good as its READABLE form — `set-kb findability`
discovers every readable `.md` that sits next to a `.jsonl` recording (same
stem, or the same date-and-part prefix), plus every file the project names in
`findability.globs`, and verifies two things per file:

  level 1 — it IS indexed; a miss names the rule that excludes it (AC: a
            recording hidden by an exclusion must not fail silently);
  level 2 — a query built ONLY from its title or first heading returns it in
            the top k (default 10). Stopwords removed, no words taken from the
            path — the path is the thing being found, so a query that quotes
            it would test the path, not the retrieval.

Deterministic, no model, no network. Discovery walks the whole project except
the PERMANENT plumbing (`.git`, `.set`) and the DEFAULT generated-tree groups
(dependencies, build output, virtualenvs, vendored trees, agent logs) — the
trees where recordings do not live. Deliberately NOT pruned: anything the
PROJECT configured. A project pattern that hides a recording must be caught
here, which is only possible if discovery does not apply it.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from set_kb.config import DEFAULT_EXCLUSION_GROUPS, KbConfig
from set_kb.frontmatter import parse_frontmatter
from set_kb.glob import glob_to_re
from set_kb.indexer import PERMANENT_PRUNE, exclusion_rule
from set_kb.lang import language_pack
from set_kb.search import search_page, tokenize
from set_kb.store import SqliteFtsStore

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 10

_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
_PART_SUFFIX_RE = re.compile(r"(-raw)?-part\d+$")

# The discovery prune: plumbing + the default GENERATED-tree groups. Project
# exclusions are deliberately absent — see the module docstring.
_DISCOVERY_PRUNE = list(DEFAULT_EXCLUSION_GROUPS)


def recording_key(stem: str) -> "str | None":
    """The date-and-part identity of a recording name: the trailing
    `-partN` / `-raw-partN` / `-raw` decoration stripped, then date + first
    name part. `2026-09-30-copilot-raw-part1` and `2026-09-30-copilot` share
    an identity; a stem without a name part after the date matches on the bare
    date; a stem without a date prefix matches by stem alone."""
    s = _PART_SUFFIX_RE.sub("", stem.lower())
    s = re.sub(r"-raw$", "", s)
    m = _DATE_RE.match(s)
    if m:
        date, rest = m.groups()
        return f"{date}-{rest.split('-', 1)[0]}"
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


@dataclass
class Candidate:
    path: str  # repository-relative, NFC, POSIX
    kind: str  # "recording" | "glob"
    recording: "str | None" = None  # the .jsonl sibling that named it


@dataclass
class CandidateResult:
    candidate: Candidate
    indexed: bool
    reason: "str | None" = None  # why level 1 failed
    title: "str | None" = None
    query: "str | None" = None
    rank: "int | None" = None  # 1-based position in the top k; None = missed
    note: "str | None" = None


@dataclass
class FindabilityReport:
    results: list = field(default_factory=list)
    top_k: int = DEFAULT_TOP_K
    notes: list = field(default_factory=list)  # how the index was produced (snapshot, …)
    # Candidates a structural frontmatter rule excludes (agent-session dumps,
    # spec AC-7). Excluded BY DESIGN, so they are neither level-1 misses nor
    # part of `results` — but they are named, because silence would read as
    # "the candidate was never seen".
    excluded_by_design: list = field(default_factory=list)

    @property
    def level1_missed(self) -> list:
        return [r for r in self.results if not r.indexed]

    @property
    def level2_checked(self) -> list:
        return [r for r in self.results if r.indexed and r.query]

    @property
    def level2_found(self) -> list:
        return [r for r in self.level2_checked if r.rank is not None]

    @property
    def ok(self) -> bool:
        return not self.level1_missed

    def to_json_dict(self, root: str) -> dict:
        return {
            "version": 1,
            "command": "findability",
            "root": root,
            "ok": self.ok,
            "topK": self.top_k,
            "notes": list(self.notes),
            "excludedByDesign": [
                {
                    "path": r.candidate.path,
                    "kind": r.candidate.kind,
                    "recording": r.candidate.recording,
                    "reason": r.reason,
                }
                for r in self.excluded_by_design
            ],
            "level1": {"checked": len(self.results), "missed": len(self.level1_missed)},
            "level2": {
                "checked": len(self.level2_checked),
                "found": len(self.level2_found),
                "rate": round(len(self.level2_found) / len(self.level2_checked), 4) if self.level2_checked else None,
            },
            "candidates": [
                {
                    "path": r.candidate.path,
                    "kind": r.candidate.kind,
                    "recording": r.candidate.recording,
                    "indexed": r.indexed,
                    "reason": r.reason,
                    "title": r.title,
                    "query": r.query,
                    "rank": r.rank,
                    "note": r.note,
                }
                for r in self.results
            ],
        }


# ── discovery ────────────────────────────────────────────────────────────────


def _walk_names(dir: str, base: str, prune: list, out: dict) -> None:
    """Per-directory {".md": [...], ".jsonl": [...]} under `base`, skipping the
    discovery prune. Read-only — discovery never touches a store."""
    try:
        entries = sorted(os.scandir(dir), key=lambda e: e.name)
    except (FileNotFoundError, NotADirectoryError):
        return
    for e in entries:
        abs = os.path.join(dir, e.name)
        rel = os.path.relpath(abs, base).replace(os.sep, "/")
        if PERMANENT_PRUNE.search(rel):
            continue
        if e.is_dir(follow_symlinks=False):
            if any(rx.search(rel + "/x") for rx in prune):
                continue
            _walk_names(abs, base, prune, out)
        else:
            stem, ext = os.path.splitext(e.name)
            if ext in (".md", ".jsonl"):
                out.setdefault(os.path.dirname(abs) or ".", {}).setdefault(ext, []).append((stem, abs))


def discover(project_root: str, cfg: KbConfig) -> list:
    """Every saved recording's readable form, plus the project's own
    findability globs. A `.md` is a recording's readable form when its folder
    holds a `.jsonl` with the same stem or the same date-and-part prefix."""
    prune = [glob_to_re(p) for _name, pats in _DISCOVERY_PRUNE for p in pats]
    names: dict = {}
    _walk_names(str(project_root), str(project_root), prune, names)
    found: dict = {}
    for dir, by_ext in names.items():
        jsonls = by_ext.get(".jsonl", [])
        for stem, abs in by_ext.get(".md", []):
            rel = unicodedata.normalize("NFC", os.path.relpath(abs, project_root).replace(os.sep, "/"))
            mate = next(
                (jstem for jstem, _jabs in jsonls if jstem == stem or (recording_key(stem) and recording_key(stem) == recording_key(jstem))),
                None,
            )
            if mate is not None:
                found[rel] = Candidate(path=rel, kind="recording", recording=f"{mate}.jsonl")
    for pattern in cfg.findability_globs:
        try:
            matches = Path(project_root).glob(pattern)
        except ValueError as e:  # a malformed glob is a loud config problem
            raise ValueError(f"findability glob {pattern!r}: {e}") from e
        for abs in matches:
            if not abs.is_file():
                continue
            rel = unicodedata.normalize("NFC", os.path.relpath(abs, project_root).replace(os.sep, "/"))
            if PERMANENT_PRUNE.search(rel):
                continue
            found.setdefault(rel, Candidate(path=rel, kind="glob"))
    return [found[k] for k in sorted(found)]


# ── the checks ───────────────────────────────────────────────────────────────


def _title_of(abs_path: str) -> "str | None":
    """The file's title: frontmatter `title`, else the first ATX heading.
    None when the file names itself in neither form."""
    try:
        text = Path(abs_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    parsed = parse_frontmatter(text)
    if parsed.fm:
        t = parsed.fm.get("title")
        if isinstance(t, str) and t.strip():
            return t.strip()
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if m:
            return m.group(1)
    return None


def _level1_reason(project_root, cfg, index_opts, ledger, candidate: Candidate) -> "str | None":
    """The first reason the candidate is not indexed, in the indexer's
    decision order — extension, plumbing, pattern, frontmatter, ledger —
    checked under EVERY configured root it lives under (roots nest, and a
    root-scoped pattern fires under one root only)."""
    ext = os.path.splitext(candidate.path)[1].lower()
    if ext not in [e.lower() for e in cfg.extensions]:
        return f"extension {ext or '(none)'} is not indexed (config.extensions: {', '.join(cfg.extensions)})"
    for s in cfg.sources:
        if s.ref and not candidate.path.startswith(s.ref + "/"):
            continue
        root_rel = candidate.path[len(s.ref) + 1 :] if s.ref else candidate.path
        abs_path = os.path.join(str(project_root), candidate.path.replace("/", os.sep))
        ledger_key = f"{s.ref}/{root_rel}" if s.ref else root_rel
        rule, _digest = exclusion_rule(abs_path, root_rel, index_opts, ledger=ledger, ledger_key=ledger_key)
        if rule:
            return rule
    return None


def run_findability(project, top_k: int = DEFAULT_TOP_K) -> FindabilityReport:
    """Refresh once, then check every candidate against the index the way a
    search would serve it. Level-1 misses decide `ok`; the caller exits
    non-zero on them."""
    from set_kb.lifecycle import refresh  # local import: lifecycle imports search, not this module

    from set_kb.config import index_options as cfg_index_options

    rr = refresh(project)
    ledger = project.framework_ledger
    index_opts = cfg_index_options(project.config, framework_ledger=ledger)
    report = FindabilityReport(top_k=top_k, notes=list(rr.notes))

    store, exists = (None, os.path.exists(project.db_path))
    if exists:
        store = SqliteFtsStore(project.db_path)
        store.init()

    def indexed_under_any_root(path: str) -> bool:
        if store is None:
            return False
        for s in project.config.sources:
            if s.ref and not path.startswith(s.ref + "/"):
                continue
            root_rel = path[len(s.ref) + 1 :] if s.ref else path
            if store.get_chunks(s.ref, root_rel):
                return True
        return False

    try:
        for candidate in discover(project.root, project.config):
            reason = _level1_reason(project.root, project.config, index_opts, ledger, candidate)
            if reason is not None and reason.startswith("excludeFrontmatter:"):
                # A candidate the frontmatter rule excludes is an agent-session
                # dump (AC-7) — not a recording whose readable form went
                # missing, so it is neither a miss nor exit-relevant. Only the
                # frontmatter rule gets this treatment: a project PATTERN
                # hiding a candidate stays a level-1 miss, because that is the
                # failure findability exists to catch.
                report.excluded_by_design.append(
                    CandidateResult(candidate=candidate, indexed=False, reason=reason)
                )
                continue
            indexed = reason is None and indexed_under_any_root(candidate.path)
            if reason is None and not indexed and store is None:
                reason = "no index exists yet"
            if reason is None and not indexed:
                reason = "not in the index (no chunks recorded)"
            result = CandidateResult(candidate=candidate, indexed=indexed, reason=None if indexed else reason)
            if indexed:
                abs_path = os.path.join(str(project.root), candidate.path.replace("/", os.sep))
                title = _title_of(abs_path)
                result.title = title
                if not title:
                    result.note = "no frontmatter title and no heading — level 2 skipped"
                else:
                    tokens = tokenize(title, language_pack(project.config.language))
                    if not tokens:
                        result.note = "the title carries no searchable tokens — level 2 skipped"
                    else:
                        query = " ".join(tokens)
                        result.query = query
                        opts = _search_opts(project.config, top_k)
                        page = search_page(store, query, opts)
                        for i, h in enumerate(page.hits, 1):
                            h_rel = f"{h.root}/{h.path}" if h.root else h.path
                            if h_rel == candidate.path:
                                result.rank = i
                                break
            report.results.append(result)
    finally:
        if store is not None:
            store.close()
    return report


def _search_opts(cfg: KbConfig, top_k: int):
    """The project's own ranking for a level-2 query — findability measures
    how THIS project's configuration retrieves, not an idealised one."""
    from set_kb.config import search_options

    return search_options(cfg, limit=top_k)


__all__ = ["Candidate", "CandidateResult", "FindabilityReport", "discover", "recording_key", "run_findability"]
