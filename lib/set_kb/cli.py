"""`set-kb` — the single implementation surface of the knowledge-base engine.

Every other surface (the MCP tools, the skill, scripts) shells out to THIS
command rather than reimplementing search (design D3): one code path, and an
engine bug is fixed once. The command resolves the project from the current
directory's repository root, so it answers identically from any folder inside
the project (AC: searching from any folder in the project).

The JSON output is a STABLE CONTRACT (requirement: the-json-output-is-a-stable-
contract): every reading subcommand accepts `--json`, and the payload carries
`version`. Field names do not change without a new contract version — a script
that reads `hits[0].path` keeps working, and `set-kb get` accepts that path
unchanged.

Exit codes: 0 = answered; 1 = answered with findings (zero results is NOT a
finding, but a failed findability check or an ambiguous section is); 2 = could
not run (no project, config error, runtime without FTS5). The distinction is
what lets a script tell "your question has no answer" from "ask correctly".
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

from set_kb.config import CONFIG_REL, ConfigError, LEGACY_REL, index_options, load_config, read_framework_ledger
from set_kb.eval import DEFAULT_GOLDEN_REL, EvalError, golden_path_for, load_golden, run_eval
from set_kb.get_section import leaf_of, resolve_section
from set_kb.indexer import IndexSource, scan_exclusions
from set_kb.findability import run_findability
from set_kb.lifecycle import ProjectError, load_project, refresh, search_project
from set_kb.project import ensure_ignored, index_paths, resolve_root
from set_kb.runtime import KbRuntimeError, ensure_runtime
from set_kb.store import SqliteFtsStore

logger = logging.getLogger(__name__)

CONTRACT_VERSION = 1

PROG = "set-kb"

# from set_kb.findability — re-exported for the CLI default
DEFAULT_TOP_K = 10


# ── shared helpers ───────────────────────────────────────────────────────────


def repo_rel(root_id: str, root_path: str) -> str:
    """The REPOSITORY-relative path of an indexed (root, root-relative path)
    pair — the form every hit on a page and every `get` argument speaks. The
    engine stores paths root-relative (an index must not care where its roots
    hang), the CLI contract is repo-relative (a script must not need the
    config to resolve a hit)."""
    return f"{root_id}/{root_path}" if root_id else root_path


def normalize_path_input(project_root: str, raw: str) -> str:
    """Accept a repo-relative path as printed, or an absolute path inside the
    project (a path copied from a tool output). NFC + POSIX separators — the
    same normalisation the indexer applied, so the lookup can hit."""
    p = raw.strip()
    if os.path.isabs(p):
        p = os.path.relpath(p, project_root)
    p = p.replace(os.sep, "/")
    p = re.sub(r"^\./", "", p)
    return unicodedata.normalize("NFC", p)


def open_index(project) -> "tuple[SqliteFtsStore, bool]":
    """Open the project's index for reading; `(None-able store, exists)`. A
    missing index is an HONEST state (nothing indexed yet), not an error — the
    caller states it instead of pretending to have searched."""
    if not os.path.exists(project.db_path):
        return None, False
    store = SqliteFtsStore(project.db_path)
    store.init()
    return store, True


def emit_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def refresh_phrase(refreshed: bool, snapshot: bool, no_reindex: bool, notes: list) -> str:
    if no_reindex:
        return "not refreshed (--no-reindex)"
    if snapshot:
        return "not refreshed — a concurrent refresh holds the lock; results are from the current snapshot"
    if refreshed:
        return "refreshed before this search"
    return "not refreshed"


# ── search (the page the whole framework reads) ──────────────────────────────


def render_hit_line(index: int, hit) -> list:
    meta = [m for m in (hit.channel, hit.scope) if m]
    lines = [
        f"{index:>3}. {repo_rel(hit.root, hit.path)} › {hit.heading_path}"
        + (f"  [{', '.join(meta)}]" if meta else "")
    ]
    if hit.snippet:
        lines.append(f"     {hit.snippet}")
    extras = []
    if hit.suppressed_sections:
        extras.append(f"{hit.suppressed_sections} more matching section(s) in this file")
    if hit.aka_paths:
        extras.append("duplicate content at " + ", ".join(hit.aka_paths))
    if hit.parent:
        extras.append(f"under {hit.parent.get('headingPath')}")
    if extras:
        lines.append("     (" + "; ".join(extras) + ")")
    return lines


def render_search_text(ps, query: str) -> str:
    lines: list = []
    if not ps.hits:
        # AC: zero hits — the page prints the exact query, so the absence can
        # be quoted as evidence, followed by what was NOT searched.
        lines.append(f'no hits for "{query}"')
        lines.append("")
    for i, h in enumerate(ps.hits, 1):
        lines.extend(render_hit_line(i, h))
    shown = len(ps.hits)
    beyond = max(0, ps.page.total - shown)
    lines.append("")
    if beyond:
        lines.append(f"showing {shown} of {ps.page.total} matching sources — {beyond} more match")
    else:
        lines.append(f"{ps.page.total} matching source(s)")
    lines.append(f"paths relative to: {ps.root}")
    lines.append("index: " + refresh_phrase(ps.refreshed, ps.snapshot, ps.no_reindex, ps.notes))
    for line in ps.page.exclusions:
        lines.append(line)
    for n in ps.notes:
        lines.append(f"note: {n}")
    return "\n".join(lines)


def search_payload(ps, query: str) -> dict:
    """The JSON contract: version, the footer facts as fields, and per hit the
    repo-relative path, heading path, leaf heading, snippet, score, channel,
    scope, further-matching-section count and duplicate count."""
    d = ps.to_json_dict()
    d["version"] = CONTRACT_VERSION
    d["command"] = "search"
    d["query"] = query
    d["snapshot"] = ps.snapshot
    d["noReindex"] = ps.no_reindex
    by_chunk = {(h.root, h.chunk_id): h for h in ps.hits}
    for hd in d["hits"]:
        h = by_chunk.get((hd.get("root"), hd.get("chunkId")))
        if h is None:
            continue
        hd["path"] = repo_rel(h.root, h.path)
        hd["heading"] = leaf_of(h.heading_path)
        hd["duplicateCount"] = len(h.aka_paths) if h.aka_paths else 0
    return d


def cmd_search(args) -> int:
    project = load_project(os.getcwd())
    ps = search_project(
        project,
        args.query,
        limit=args.limit,
        root=args.root,
        channel=args.channel,
        scope=args.scope,
        exclude_paths=tuple(args.exclude_path or ()),
        lane=not args.no_lane,
        no_reindex=args.no_reindex,
        force=args.full,
    )
    if args.json:
        emit_json(search_payload(ps, args.query))
    else:
        print(render_search_text(ps, args.query))
    return 0


# ── get (verbatim section fetch) ─────────────────────────────────────────────


def locate_in_index(store, cfg, rel: str) -> "tuple[str | None, list]":
    """Map a repo-relative path onto the (root, root-relative path) that holds
    it, first configured root that has it — roots may nest (a `""` root spans
    the whole repository), so the first source carrying the path wins."""
    for s in cfg.sources:
        if s.ref and not (rel == s.ref or rel.startswith(s.ref + "/")):
            continue
        root_rel = rel[len(s.ref) + 1 :] if s.ref else rel
        chunks = store.get_chunks(s.ref, root_rel)
        if chunks:
            return s.ref, chunks
    return None, []


def cmd_get(args) -> int:
    project = load_project(os.getcwd())
    rel = normalize_path_input(project.root, args.path)
    store, exists = open_index(project)
    if not exists:
        print(f"set-kb: no index exists yet in this project — run a search first: {rel}", file=sys.stderr)
        return 1
    try:
        root_id, chunks = locate_in_index(store, project.config, rel)

        def payload(kind: str, body=None, candidates=None) -> dict:
            return {
                "version": CONTRACT_VERSION,
                "command": "get",
                "path": rel,
                "section": args.section,
                "root": root_id,
                "found": kind == "found",
                "kind": kind,
                "body": body,
                "candidates": candidates,
            }

        if not chunks:
            msg = f"set-kb: not in the index: {rel} (excluded from the corpus, or not indexed yet)"
            if args.json:
                emit_json(payload("not-indexed"))
            print(msg, file=sys.stderr)
            return 1

        if not args.section:
            # The whole file, from disk — the index addressed us here, and the
            # disk is the verbatim source (frontmatter included).
            disk = Path(project.root) / rel
            if not disk.is_file():
                msg = f"set-kb: indexed but missing on disk: {rel}"
                if args.json:
                    emit_json(payload("missing"))
                print(msg, file=sys.stderr)
                return 1
            text = disk.read_text(encoding="utf-8")
            if args.json:
                emit_json(payload("found", body=text))
            else:
                print(text, end="" if text.endswith("\n") else "\n")
            return 0

        res = resolve_section(chunks, args.section)
        if res.kind == "found":
            # ALL slices of the section — the chunker splits a >4000-char
            # section into consecutive slices sharing one heading path, and a
            # single-slice print silently truncated such a section.
            body = "\n\n".join(c.body for c in res.slices).rstrip() + "\n"
            if args.json:
                emit_json(payload("found", body=body))
            else:
                print(body, end="")
            return 0
        if res.kind == "ambiguous":
            # An ambiguous leaf lists its full heading paths and prints
            # NEITHER section (AC: ambiguous leaf heading).
            msg = "set-kb: ambiguous section %r in %s — name the full path:\n  %s" % (
                args.section,
                rel,
                "\n  ".join(res.candidates),
            )
            if args.json:
                emit_json(payload("ambiguous", candidates=list(res.candidates)))
            print(msg, file=sys.stderr)
            return 1
        msg = f"set-kb: no section {args.section!r} in {rel}"
        if args.json:
            emit_json(payload("missing"))
        print(msg, file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


# ── sources (the project's own layer descriptions) ───────────────────────────


def config_path_label(project) -> str:
    if (Path(project.root) / CONFIG_REL).is_file():
        return CONFIG_REL
    if project.config.legacy:
        return f"{LEGACY_REL} (legacy location — move to {CONFIG_REL})"
    return "built-in defaults (no project config)"


def cmd_sources(args) -> int:
    project = load_project(os.getcwd())
    cfg = project.config
    roots = [{"ref": s.ref, "priority": s.priority, "about": s.about} for s in cfg.sources]
    channels = [
        {
            "channel": c.channel,
            "roots": list(c.roots),
            "include": list(c.include) if c.include else None,
            "exclude": list(c.exclude) if c.exclude else None,
            "about": c.about,
        }
        for c in cfg.channels
    ]
    lane = {
        "channels": list(cfg.ranking.get("laneChannels", [])),
        "quota": cfg.ranking.get("laneQuota", 0.0),
        "leadMargin": cfg.ranking.get("laneLeadMargin", 0.0),
    }
    if args.json:
        emit_json(
            {
                "version": CONTRACT_VERSION,
                "command": "sources",
                "root": project.root,
                "config": config_path_label(project),
                "language": cfg.language,
                "roots": roots,
                "channels": channels,
                "lane": lane,
                "findabilityGlobs": list(cfg.findability_globs),
            }
        )
        return 0

    lines = [f"knowledge-base sources of {project.root}", f"config: {config_path_label(project)}", f"language: {cfg.language}", ""]
    lines.append("roots:")
    for s in cfg.sources:
        label = s.ref if s.ref else "(repository root)"
        about = f" — {s.about}" if s.about else ""
        lines.append(f"  {label}  (priority {s.priority}){about}")
    lines.append("")
    if cfg.channels:
        lines.append("channels (first matching rule decides):")
        for c in cfg.channels:
            about = f" — {c.about}" if c.about else ""
            inc = f"  include: {', '.join(c.include)}" if c.include else ""
            exc = f"  exclude: {', '.join(c.exclude)}" if c.exclude else ""
            lines.append(f"  {c.channel}  roots: {', '.join(c.roots)}{inc}{exc}{about}")
    else:
        lines.append("channels: none configured")
    lines.append("")
    lane_channels = cfg.ranking.get("laneChannels", [])
    if lane_channels:
        lines.append(
            "reserved lane: %s @ %.0f%% of the page (lead margin %.2f)"
            % (", ".join(lane_channels), cfg.ranking.get("laneQuota", 0.0) * 100, cfg.ranking.get("laneLeadMargin", 0.0))
        )
    else:
        lines.append("reserved lane: none (ranking by score alone)")
    if cfg.findability_globs:
        lines.append(f"findability globs: {', '.join(cfg.findability_globs)}")
    print("\n".join(lines))
    return 0


# ── index (explicit build/refresh) ───────────────────────────────────────────


def cmd_index(args) -> int:
    project = load_project(os.getcwd())
    rr = refresh(project, force=args.full, no_reindex=False)
    stats = rr.stats or {}
    if args.json:
        emit_json({"version": CONTRACT_VERSION, "command": "index", "root": project.root, "seeded": rr.seeded, **{k: stats.get(k) for k in ("scanned", "changed", "deleted", "chunks", "excluded", "counts")}})
        return 0
    excluded = stats.get("excluded") or {}
    print(
        f"indexed {project.root}: scanned {stats.get('scanned', 0)}, changed {stats.get('changed', 0)}, "
        f"deleted {stats.get('deleted', 0)}, chunks {stats.get('counts', {}).get('chunks', stats.get('chunks', 0))}"
    )
    if rr.seeded:
        print("seeded from the main checkout's index")
    if excluded:
        print("excluded: " + ", ".join(f"{rule} ({n})" for rule, n in sorted(excluded.items())))
    return 0


# ── doctor (whether search works in THIS project) ────────────────────────────


def _age_text(seconds: float) -> str:
    for unit, div in (("days", 86400), ("hours", 3600), ("minutes", 60)):
        if seconds >= div:
            return f"{seconds / div:.0f} {unit} ago"
    return f"{max(0, int(seconds))} s ago"


def cmd_doctor(args) -> int:
    """Health check: Python, FTS5, config, git-ignore status, index presence
    and freshness, corpus counts per root and channel, excluded-file counts
    per rule. Blocking findings exit non-zero; everything else reports.

    The exclusion census is a fresh whole-tree scan (`scan_exclusions`), not
    the last refresh's stats: the incremental path cheap-skips unchanged files
    BEFORE their content rules run, so quoting refresh stats would report the
    corpus as it was measured on some earlier day."""
    checks: list = []

    def check(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    blocked = False
    root = None
    try:
        root = resolve_root(os.getcwd())
        check("project", "ok", root)
    except ProjectError as e:
        blocked = True
        check("project", "blocked", str(e))
        _report_doctor(args, checks)
        return 1

    py = sys.version_info
    if (py.major, py.minor) >= (3, 10):
        check("python", "ok", f"{py.major}.{py.minor}.{py.micro} (requires >= 3.10)")
    else:
        blocked = True
        check("python", "blocked", f"{py.major}.{py.minor}.{py.micro} — the engine requires Python >= 3.10")

    try:
        info = ensure_runtime()
        check("runtime", "ok", f"SQLite {info['sqlite']} — FTS5 + 'porter unicode61' tokenizer available")
    except KbRuntimeError as e:
        blocked = True
        check("runtime", "blocked", str(e))

    db_path, _lock_path = index_paths(root)
    cfg = None
    try:
        cfg = load_config(root)
        check("config", "ok", config_path_label_for(root, cfg))
    except ConfigError as e:
        blocked = True
        check("config", "blocked", str(e))

    try:
        ensure_ignored(root, db_path)
        check("ignore", "ok", f"{os.path.relpath(db_path, root)} is ignored by git")
    except ProjectError as e:
        blocked = True
        check("ignore", "blocked", str(e))

    index_info: dict = {"present": False}
    roots_table: list = []
    channels_table: list = []
    store, exists = None, os.path.exists(db_path)
    if exists:
        age = time.time() - os.path.getmtime(db_path)
        try:
            store = SqliteFtsStore(db_path)
            store.init()
            counts = store.counts()
            index_info = {"present": True, "writtenAgoSeconds": round(age), "counts": counts}
            check(
                "index",
                "ok" if counts["files"] else "warn",
                f"present — {counts['files']} files, {counts['chunks']} chunks (written {_age_text(age)})",
            )
            roots_table = store.root_counts()
            channels_table = store.channel_counts()
        except sqlite3.DatabaseError as e:
            # An unreadable index is a finding, not a crash — the next search
            # rebuilds it, and doctor says so instead of dying.
            check("index", "warn", f"present but unreadable ({e}) — the next search rebuilds it")
        finally:
            if store is not None:
                store.close()
    else:
        check("index", "warn", "not built yet — the first search builds it")

    census: dict = {}
    if cfg is not None:
        sources = [IndexSource(root=s.ref, dir=os.path.join(root, s.ref)) for s in cfg.sources]
        census = scan_exclusions(sources, index_options(cfg, framework_ledger=read_framework_ledger(root)))
        missing = [s.id for s in sources if not os.path.isdir(s.dir)]
        if missing:
            check("sources", "warn", f"configured root(s) missing on disk: {', '.join(missing)}")
        rules = sorted(census.get("excluded", {}).items(), key=lambda kv: -kv[1])
        if rules:
            detail = "; ".join(f"{rule}: {n} file(s)" for rule, n in rules)
            check("exclusions", "info", detail)
        else:
            check("exclusions", "info", "nothing excluded — every candidate is indexed")

    _report_doctor(args, checks, root=root, index=index_info, roots=roots_table, channels=channels_table, census=census)
    return 1 if blocked else 0


def config_path_label_for(root, cfg) -> str:
    if (Path(root) / CONFIG_REL).is_file():
        return CONFIG_REL
    if cfg.legacy:
        return f"{LEGACY_REL} (legacy — move to {CONFIG_REL})"
    return "built-in defaults (no project config)"


def _report_doctor(args, checks: list, root=None, index=None, roots=None, channels=None, census=None) -> None:
    glyph = {"ok": "ok  ", "warn": "warn", "info": "info", "blocked": "BLOCKED"}
    if args.json:
        emit_json(
            {
                "version": CONTRACT_VERSION,
                "command": "doctor",
                "root": root,
                "ok": all(c["status"] != "blocked" for c in checks),
                "checks": checks,
                "index": index,
                "roots": [
                    {"root": r, "files": f, "chunks": c}
                    for r, f, c in (roots or [])
                ],
                "channels": [
                    {"channel": c, "files": f, "chunks": n}
                    for c, f, n in (channels or [])
                ],
                "exclusions": [{"rule": rule, "files": n} for rule, n in sorted((census or {}).get("excluded", {}).items(), key=lambda kv: -kv[1])],
            }
        )
        return
    if root:
        print(f"set-kb doctor — {root}")
    for c in checks:
        print(f"  {glyph.get(c['status'], '    ')} {c['name']}: {c['detail']}")
    for r, f, n in roots or []:
        label = r if r else "(repository root)"
        print(f"  root {label}: {f} files, {n} chunks")
    for c, f, n in channels or []:
        label = c if c else "(unclassified)"
        print(f"  channel {label}: {f} files, {n} chunks")
    for rule, n in sorted((census or {}).get("excluded", {}).items(), key=lambda kv: -kv[1]):
        print(f"  excluded by {rule}: {n} file(s)")


# ── findability (recordings and named notes must be findable) ────────────────


def cmd_findability(args) -> int:
    project = load_project(os.getcwd())
    report = run_findability(project, top_k=args.top or DEFAULT_TOP_K)
    if args.json:
        emit_json(report.to_json_dict(project.root))
    else:
        recordings = sum(1 for r in report.results if r.candidate.kind == "recording")
        globs = len(report.results) - recordings
        print(f"set-kb findability — {project.root}")
        print(f"  candidates: {len(report.results)} ({recordings} recording(s), {globs} from globs)   top-k = {report.top_k}")
        for n in report.notes:
            print(f"  note: {n}")
        if report.excluded_by_design:
            print(f"  excluded by design: agent-session dumps — {len(report.excluded_by_design)}")
            for r in report.excluded_by_design:
                print(f"    {r.candidate.path} — {r.reason}")
        l1_missed = report.level1_missed
        print(f"  level 1 — indexed: {len(report.results) - len(l1_missed)}/{len(report.results)}")
        for r in l1_missed:
            print(f"    MISS {r.candidate.path} — {r.reason}")
        l2_checked = report.level2_checked
        l2_found = report.level2_found
        if l2_checked:
            rate = 100.0 * len(l2_found) / len(l2_checked)
            print(f"  level 2 — title query in the top {report.top_k}: {len(l2_found)}/{len(l2_checked)} found ({rate:.0f}%)")
            for r in l2_checked:
                if r.rank is None:
                    where = f"rank {r.rank}" if r.rank else "not in the top %d" % report.top_k
                    print(f"    MISS {r.candidate.path} — query {r.query!r} → {where}")
        elif report.results:
            print("  level 2 — nothing to query (no candidate carries a title or heading)")
    return 0 if report.ok else 1


# ── eval (golden set, control arm, fail-closed denominator) ──────────────────


def cmd_eval(args) -> int:
    project = load_project(os.getcwd())
    golden_file = golden_path_for(project.root, args.golden)
    pairs, control = load_golden(golden_file)
    if args.control_query:
        control = {"q": args.control_query, "targets": list(args.control_target or [])}
    report = run_eval(project, pairs, k=args.k, lane=not args.no_lane, control=control, no_reindex=args.no_reindex)
    report.golden = os.path.relpath(golden_file, project.root)
    if args.json:
        emit_json(report.to_json_dict(project.root))
    else:
        m = report.metrics()
        lane_channels = project.config.ranking.get("laneChannels", [])
        print(f"set-kb eval — {project.root}")
        print(
            f"  golden set: {report.golden} — {len(report.results)} pair(s), k = {report.k}, "
            f"lane {'on (' + ', '.join(lane_channels) + ')' if (not args.no_lane and lane_channels) else 'off'}"
        )
        for n in report.notes:
            print(f"  note: {n}")
        print(
            "  recall@{k}: {recall:.3f}   MRR: {mrr:.3f}   rank-1: {r1:.1%}   top-3: {t3:.1%}   top-5: {t5:.1%}".format(
                k=report.k, recall=m["recallAtK"], mrr=m["mrr"], r1=m["rank1"], t3=m["top3"], t5=m["top5"]
            )
        )
        failures = report.failures
        if failures:
            print(f"  failures: {len(failures)} (counted as misses — the denominator stays {len(report.results)})")
            for r in failures:
                print(f"    FAIL {r.id}: {r.error}")
        if report.control_q is not None:
            control_recall = (
                f"recall@{report.k} {report.control_found}/{report.control_targets} = {report.control_found / report.control_targets:.3f}"
                if report.control_found is not None and report.control_targets
                else "no recall (no targets configured)"
            )
            print(f'  control arm: query "{report.control_q}" — {control_recall}')
            if report.control_note:
                print(f"    note: {report.control_note}")
        misses = report.misses
        if misses:
            print(f"  misses ({len(misses)}):")
            for r in misses:
                print(f"    {r.id} {r.q!r} → best rank none (found {r.found}/{len(r.targets)} targets)")
    return 0


# ── argument parsing ─────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROG, description="Project knowledge-base search (markdown, section-level)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output (stable contract, versioned)")
    common.add_argument("--verbose", action="store_true", help="debug logging on stderr")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("index", parents=[common], help="build or refresh the index")
    p.add_argument("--full", action="store_true", help="re-chunk every file, not only changed ones")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("search", parents=[common], help="ranked section search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--root", default=None, help="restrict to one configured source root")
    p.add_argument("--channel", default=None, help="restrict to one configured channel")
    p.add_argument("--scope", default=None, help="restrict to one captured scope (name=value)")
    p.add_argument("--exclude-path", action="append", default=None, help="exclude path fragments (repeatable)")
    p.add_argument("--no-lane", action="store_true", help="disable the reserved channel lane for this search")
    p.add_argument("--no-reindex", action="store_true", help="query the index as it stands")
    p.add_argument("--full", action="store_true", help="force a full re-chunk before searching")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("get", parents=[common], help="print a file, or one section of it, verbatim")
    p.add_argument("path", help="repository-relative path (a hit's path, unchanged)")
    p.add_argument("--section", default=None, help="heading path, or an unambiguous leaf heading")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("sources", parents=[common], help="roots, channels and the lane, with the config's own descriptions")
    p.set_defaults(func=cmd_sources)

    p = sub.add_parser("doctor", parents=[common], help="whether search works in this project (blocking vs informational checks)")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("findability", parents=[common], help="saved recordings and named notes must be indexed and retrievable")
    p.add_argument("--top", type=int, default=None, help="top-k for the title query (default 10)")
    p.set_defaults(func=cmd_findability)

    p = sub.add_parser("eval", parents=[common], help="retrieval eval over the project's golden set, with a control arm")
    p.add_argument("--golden", default=None, help=f"golden-set path (default {DEFAULT_GOLDEN_REL})")
    p.add_argument("--k", type=int, default=10, help="top-k the metrics measure (default 10)")
    p.add_argument("--no-lane", action="store_true", help="disable the reserved lane for every query in this run")
    p.add_argument("--no-reindex", action="store_true", help="measure the index as it stands (no refresh)")
    p.add_argument("--control-query", default=None, help="run this fixed control query as the control arm")
    p.add_argument("--control-target", action="append", default=None, help="a target path for --control-query (repeatable)")
    p.set_defaults(func=cmd_eval)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.WARNING,
        format="set-kb: %(message)s",
        stream=sys.stderr,
    )
    try:
        return args.func(args)
    except (ProjectError, ConfigError, KbRuntimeError, EvalError, FileNotFoundError) as e:
        # The error a caller shows is the engine's words plus ours — the MCP
        # layer returns this text verbatim (requirement: engine failure
        # surfaces), so the message must be complete on one channel.
        print(f"{PROG}: {e}", file=sys.stderr)
        return 2
