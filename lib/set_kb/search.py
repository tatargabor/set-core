# Ported from an MIT-licensed upstream retrieval engine — see LICENSE-UPSTREAM in this package for the notice, the upstream commit and the port lineage.
"""The ranked query: BM25 over weighted fields (BM25F), exact-content dedup,
one-slot-per-source dedup, the reserved channel lane, MMR diversity, and the
distinct-source total a result page reports.

DIVERGENCE (design D8 of the change): when `lane_channels` is EMPTY there is
NO reserved lane. The reference falls back to a lane for agent-instruction
files (`doc_type='agents'`), which on a project corpus would reserve the page
for CLAUDE.md-type files. With channels named, the lane is theirs — behaviour
identical to the reference, which is what the oracle pins.

The FTS5 query is an OR of the quoted terms (recall + BM25 ranks). The
tokenizer accepts every letter/number in any script — upstream's ASCII-only
regex was a wipe-out over an accented corpus (zero tokens → zero hits) — and
all three tokenizing sites share it.
"""

from __future__ import annotations

import functools
import logging
import math
import re
import unicodedata
from typing import Optional

from set_kb.lang import ENGLISH_STOPWORDS, LanguagePack
from set_kb.store import BODY_COLUMN_INDEX, SqliteFtsStore, bm25_weights, build_filter_clauses
from set_kb.types import KbHit, SearchOpts, SearchPage

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"[^\W_]{2,}", re.UNICODE)

MIN_FEEDBACK_DOCS = 5  # minimum first-pass candidates before PRF mining is meaningful
STEM_MIN = 4


def raw_tokens(s: str) -> list:
    """Lower-cased word tokens, no stopword filtering — the raw form both the
    query and the body side share."""
    return TOKEN_RE.findall(s.lower())


def tokenize(s: str, lang: Optional[LanguagePack] = None) -> list:
    """Query tokens: raw tokens minus the language pack's function words, then
    the pack's optional stem (absent in every shipped pack). Without a pack the
    behaviour is upstream's: English function words only."""
    stop = lang.stopwords if lang is not None else ENGLISH_STOPWORDS
    kept = [t for t in raw_tokens(s) if t not in stop]
    return [lang.stem(t) for t in kept] if lang is not None and lang.stem else kept


def fold(t: str) -> str:
    """Diacritic-folded form, used ONLY where our own tokens are compared to
    each other. Both sides are folded, so this can never disagree with the
    index the way a normalization applied BEFORE the MATCH could: the
    accent-insensitivity itself stays FTS5's `unicode61` job — we do not fold
    what we hand to SQLite. Needed because FTS5 matches an accent-less query
    against an accented body, so a hit's body legitimately carries a form the
    query never spelled."""
    return "".join(ch for ch in unicodedata.normalize("NFD", t) if not unicodedata.combining(ch))


def to_match(q: str, lang: Optional[LanguagePack] = None) -> str:
    terms = tokenize(q, lang)
    # Fallback arm: fires when the query is nothing BUT function words. It has
    # to use the same Unicode class — with an ASCII regex this arm was the
    # second silent zero-hit path, and it fires exactly on the accented case.
    kept = terms if terms else raw_tokens(q)
    return " OR ".join(f'"{t}"' for t in kept)


def expand_query(query: str, opts: SearchOpts) -> str:
    """Query expansion. synonym = curated glossary; off/agent = pass-through
    (the caller already reformulated). `prf` is NOT handled here: it needs a
    first retrieval pass, so `search` owns it."""
    if opts.query_expansion != "synonym" or not opts.synonyms:
        return query
    extra = []
    for t in tokenize(query, opts.language):
        extra.extend(opts.synonyms.get(t) or [])
    return f"{query} {' '.join(extra)}" if extra else query


def has_stem(tokens: set, term: str) -> bool:
    """Stem-tolerant membership: FTS5 indexes porter stems while `tokenize`
    yields raw tokens, so the stem must count as covering the raw form. The
    prefix arm is bounded to a shared stem of at least STEM_MIN characters — an
    unbounded prefix test saturates coverage (every candidate "covers" every
    short term) and collapses the rerank into noise."""
    if term in tokens:
        return True
    if len(term) < STEM_MIN:
        return False
    for t in tokens:
        if len(t) < STEM_MIN:
            continue
        if t.startswith(term) or term.startswith(t):
            return True
    return False


def proximity_delta(query_terms: list, body: str) -> float:
    """Proximity/in-order boost: reward hits whose query terms appear close and
    in query order in the body. Returns a delta to ADD to the bm25 score
    (negative = better). bm25 is asc (lower=better), so a good proximity lowers
    the score. Both sides are folded because FTS5 matched them folded."""
    if len(query_terms) < 2:
        return 0.0
    tokens = [fold(t) for t in raw_tokens(body)]
    pos: dict = {}
    for i, t in enumerate(tokens):
        pos.setdefault(t, []).append(i)
    # smallest window containing all query terms in order
    best = float("inf")
    qt = [fold(t) for t in query_terms]

    def walk(idx: int, start: int, span: float) -> None:
        nonlocal best
        if idx == len(qt):
            best = min(best, span)
            return
        arr = pos.get(qt[idx])
        if not arr:
            return
        for p in arr:
            if p < start:
                continue
            walk(idx + 1, p, 0 if idx == 0 else span + (p - start))
            if best == 1:
                return

    walk(0, -1, 0)
    if best == float("inf"):
        return 0.0
    # window 1..~40 → delta 0..-2 (closer = bigger boost)
    return -max(0.0, 2 - best / 20)


def interleave_lanes(main: list, reserved: list, share: float, limit: int, dedup_sources: bool, lead_first: bool = False) -> list:
    """Interleave a reserved-share lane with the unrestricted lane. A source
    already emitted by either lane is never repeated, and a lane that runs dry
    yields its remaining slots to the other."""
    out: list = []
    seen: set = set()
    mi = ri = taken = 0

    def next_unseen(arr, i):
        if not dedup_sources:
            return i
        while i < len(arr) and f"{arr[i].root}\u001f{arr[i].path}" in seen:
            i += 1
        return i

    while len(out) < limit:
        mi = next_unseen(main, mi)
        ri = next_unseen(reserved, ri)
        m_has = mi < len(main)
        r_has = ri < len(reserved)
        if not m_has and not r_has:
            break
        # Slot 1 is decided by the lead rule; slots 2..N by the running share.
        # The lead pick is an ordinary reserved take — it increments `taken`
        # and populates `seen`, so slot 2 then reads 2/2 = 1 > share and yields.
        want_reserved = r_has and (
            not m_has or (len(out) == 0 and lead_first) or (taken + 1) / (len(out) + 1) <= share
        )
        if want_reserved:
            pick = reserved[ri]
            ri += 1
            taken += 1
        else:
            pick = main[mi]
            mi += 1
        if dedup_sources:
            seen.add(f"{pick.root}\u001f{pick.path}")
        out.append(pick)
    return out


def mmr(ranked: list, bodies: dict, lam: float, limit: int, lang: Optional[LanguagePack] = None) -> list:
    """Lexical MMR diversification over an already-ranked list."""
    if len(ranked) <= limit:
        return ranked

    def tok(h):
        return set(tokenize(bodies.get(f"{h.root}\u001f{h.chunk_id}", h.heading_path), lang))

    sets = {f"{h.root}\u001f{h.chunk_id}": tok(h) for h in ranked}

    def jaccard(a: set, b: set) -> float:
        inter = len(a & b)
        uni = len(a) + len(b) - inter
        return inter / uni if uni else 0.0

    out = [ranked[0]]
    remaining = ranked[1:]
    while len(out) < limit and remaining:
        best_i, best_score = 0, float("-inf")
        for i, h in enumerate(remaining):
            rel = -h.score  # higher bm25-relevance = better
            max_sim = max((jaccard(sets[f"{h.root}\u001f{h.chunk_id}"], sets[f"{o.root}\u001f{o.chunk_id}"]) for o in out), default=0.0)
            score = lam * rel - (1 - lam) * max_sim
            if score > best_score:
                best_score, best_i = score, i
        out.append(remaining.pop(best_i))
    return out


def _num(v, dflt: float, lo: float, hi: float) -> float:
    """Coerce numerics that get interpolated into SQL (bm25 weights, LIMIT) to
    finite, bounded numbers — never trust raw config/flag values in a SQL
    string."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return dflt
    return min(hi, max(lo, n)) if n == n and abs(n) != float("inf") else dflt


class _Clauses:
    """WHERE clauses + bound args shared by the ranked passes and by
    `count_sources`. ONE builder, because a count taken over a different row
    set than the page is worse than no count at all — it would state a total
    the page cannot be reconciled with."""

    def __init__(self, match: str, opts: SearchOpts, lane: Optional[dict] = None):
        where = ["chunks MATCH ?"]
        args: list = [match]
        if opts.root:
            where.append("root = ?")
            args.append(opts.root)
        if lane and lane.get("doc_type"):
            where.append("doc_type = ?")
            args.append(lane["doc_type"])
        if lane and lane.get("channels"):
            where.append("channel IN (" + ",".join("?" for _ in lane["channels"]) + ")")
            args.extend(lane["channels"])
        # Working-directory exclusion. ⚠ It belongs HERE, in the SQL WHERE, and
        # never as a post-filter over the returned page: a post-filter deletes
        # slots, so the page silently drops BELOW `limit` instead of the
        # next-best hit moving up. Matched against `root/path` so a caller may
        # name either the root-relative path or the repo-relative one; `instr`
        # is a plain substring test, so no LIKE wildcard escaping can go wrong.
        for frag in opts.exclude_paths or ():
            if not frag:
                continue
            where.append("instr(root || '/' || path, ?) = 0")
            args.append(frag)
        # structured facet filters (opt-in; absent → no clause → identical query)
        f_clauses, f_args = build_filter_clauses(opts.filters, "chunks")
        where.extend(f_clauses)
        args.extend(f_args)
        # Scope restriction (`--scope client=alfa`), in the exact stored
        # "<name>=<value>" form. Same SQL-WHERE reasoning as the exclusions
        # above: a post-filter would shrink the page below `limit`. A scope
        # nothing carries (NULL `scope` never equals a value) is therefore a
        # zero-hit page stating its exclusions — the honest answer.
        if opts.scope:
            where.append("scope = ?")
            args.append(opts.scope)
        self.where = where
        self.args = args


def count_sources(store: SqliteFtsStore, query: str, opts: Optional[SearchOpts] = None) -> int:
    """Distinct matching SOURCES under the active filters and exclusions,
    before the limit and before the lane quota — the denominator the result
    page reports as `total`.

    ⚠ Deliberately counts (root, path) pairs, i.e. the same unit the page's
    `limit` counts, so "10 of 47" compares like with like. It is measured on
    the BASE match. ⚠ Exact-content dedup (`akaPaths`) can still collapse two
    of these into one rendered hit, so `total` is an upper bound on distinct
    sources shown. Erring high is the right direction here: the failure this
    exists to prevent is a reader concluding "there is nothing else"."""
    opts = opts or SearchOpts()
    match = to_match(expand_query(query, opts), opts.language)
    if not match:
        return 0
    # Mirror the MAIN pass's doc-type lane: with a doc_type filter the page
    # shows only that docType, so the total must count the same row set. The
    # reserved lane stays unmirrored on purpose: it interleaves INTO the page,
    # it does not filter it.
    cl = _Clauses(match, opts, {"doc_type": opts.doc_type} if opts.doc_type else None)
    sql = f"SELECT COUNT(*) n FROM (SELECT DISTINCT root, path FROM chunks WHERE {' AND '.join(cl.where)})"
    return store.db.execute(sql, cl.args).fetchone()["n"]


def search(store: SqliteFtsStore, query: str, opts: Optional[SearchOpts] = None) -> list:
    """Ranked search over the store. See `search_page` for the page wrapper."""
    opts = opts or SearchOpts()
    fw = opts.field_weights or {}
    # BM25F field weights. The fallbacks are 10/3/1 — the values the measured
    # run used — NOT upstream's 8/4/1 store fallback, which was a dead branch
    # that silently disagreed with the measured configuration.
    w = {
        "headingPath": _num(fw.get("headingPath", fw.get("heading_path", 10)), 10, 0, 1000),
        "heading": _num(fw.get("heading", 3), 3, 0, 1000),
        "body": _num(fw.get("body", 1), 1, 0, 1000),
    }
    limit = int(_num(opts.limit, 10, 1, 1000))
    want_dedup = opts.dedup
    want_source_dedup = opts.source_dedup
    want_coverage = opts.coverage_rerank is True
    # Source dedup collapses many sections of one file into one slot, so a pool
    # sized at `limit` would starve the page — fetch a multiple of `limit`,
    # still bounded by the pre-existing 4000 ceiling.
    fetch = min(4000, limit * 6 if want_source_dedup else limit * 4 if want_dedup else limit)
    lang = opts.language
    qterms = tokenize(query, lang)

    # --- one BM25 pass, optionally restricted to a reserved lane -------------
    def do_pass(match: str, lane: Optional[dict] = None, depth: int = fetch) -> list:
        cl = _Clauses(match, opts, lane)
        sql = (
            "SELECT root, path, chunk_id chunkId, doc_type docType, channel, scope, body_hash bodyHash, "
            "parent_chunk_id parentChunkId, heading_path headingPath, heading, body, "
            f"bm25(chunks, {bm25_weights(w['headingPath'], w['heading'], w['body'])}) score, "
            f"snippet(chunks, {BODY_COLUMN_INDEX}, '[', ']', ' … ', 12) snippet "
            f"FROM chunks WHERE {' AND '.join(cl.where)} ORDER BY score LIMIT {int(depth)}"
        )
        return store.db.execute(sql, cl.args).fetchall()

    # PRF is engine-side and is applied ONLY with coverage rerank on: expanding
    # an OR-query deepens the very dilution the rerank exists to cure.
    mode = opts.query_expansion or "off"
    match = to_match(expand_query(query, opts), lang)
    if not match:
        return []
    extra_terms: list = []
    if mode == "prf" and want_coverage:
        first_pass = do_pass(match, {"doc_type": opts.doc_type} if opts.doc_type else None)
        extra_terms = _prf_terms(store, query, qterms, first_pass, opts)
        if extra_terms:
            match = to_match(f"{query} {' '.join(extra_terms)}", lang)

    # --- lanes ----------------------------------------------------------------
    # A small layer is buried by BM25 length normalisation, so it is ranked in
    # its OWN pass and interleaved into a reserved share of the page. An
    # explicit docType bypasses the whole mechanism.
    # ⚠ DIVERGENCE (design D8): an empty `lane_channels` means NO reserved lane
    # here. The reference falls back to a `doc_type='agents'` lane, which on a
    # project corpus reserves the page for agent-instruction files.
    lane_channels = [c for c in (opts.lane_channels or ()) if c]
    lane_share = 0.0 if opts.doc_type else _num(opts.lane_quota, 0.5, 0.0, 1.0)
    main_rows = do_pass(match, {"doc_type": opts.doc_type} if opts.doc_type else None)
    reserved_rows = do_pass(match, {"channels": lane_channels}) if lane_share > 0 and lane_channels else []

    # The lead rule compares each lane's best RAW BM25(+proximity) score.
    # Neither MMR nor coverage rerank mutates `score` — they only reorder — and
    # the capture below is a MIN over the lane, so it is reorder-invariant by
    # construction.
    bodies: dict = {}
    lane_best = {"main": float("nan"), "reserved": float("nan")}

    def lane(rows, capture_key: Optional[str] = None) -> list:
        hits: list = []
        for r in rows:
            # ⚠ chunkId is NOT root-scoped (it is sha(relative path) — two roots
            # can carry the SAME id for DIFFERENT content). Every in-search map
            # that keys a row is therefore keyed `root·chunkId` — a bare
            # chunkId key made exact-content dedup group DIFFERENT bodies into
            # a false "(+N dup)".
            bodies[f"{r['root']}\u001f{r['chunkId']}"] = r["body"]
            score = r["score"]
            if opts.proximity_boost:
                score += proximity_delta(qterms, r["body"])
            # A `:meta` record (frontmatter title row, body "") can match on the
            # heading and surface with a BLANK snippet. Fill the blank; never
            # override a real snippet, and never touch the ranking.
            snippet = r["snippet"] if (r["snippet"] or "").strip() else store.snippet_fallback(r["root"], r["path"], r["body"])
            hits.append(
                KbHit(
                    root=r["root"],
                    path=r["path"],
                    heading_path=r["headingPath"],
                    chunk_id=r["chunkId"],
                    doc_type=r["docType"],
                    channel=r["channel"],
                    scope=r["scope"],
                    score=score,
                    snippet=snippet,
                    _parent_chunk_id=r["parentChunkId"],
                )
            )

        if want_dedup:
            # exact-content collapse; prefer higher-priority root, then best
            # score. Runs FIRST so `akaPaths` is computed against the full
            # candidate set — source dedup then operates over already-collapsed
            # hits.
            prio = opts.root_priority or {}
            by_chunk = {f"{r['root']}\u001f{r['chunkId']}": r for r in rows}
            groups: dict = {}
            for h in hits:
                key = by_chunk[f"{h.root}\u001f{h.chunk_id}"]["bodyHash"]
                groups.setdefault(key, []).append(h)
            hits = []
            for g in groups.values():
                g.sort(key=functools.cmp_to_key(lambda a, b: (prio.get(b.root, 0) - prio.get(a.root, 0)) or (a.score - b.score)))
                head = g[0]
                if len(g) > 1:
                    head.aka_paths = [x.path for x in g[1:]]
                hits.append(head)
            hits.sort(key=lambda h: h.score)

        if want_source_dedup:
            # One slot per (root, path); representative = best (lowest) BM25
            # score; the rest become a per-source count the render surfaces.
            groups = {}
            for h in hits:
                groups.setdefault(f"{h.root}\u001f{h.path}", []).append(h)
            hits = []
            for g in groups.values():
                g.sort(key=lambda h: h.score)
                head = g[0]
                head.suppressed_sections = len(g) - 1
                hits.append(head)
            hits.sort(key=lambda h: h.score)

        if capture_key is not None and hits:
            lane_best[capture_key] = min(h.score for h in hits)

        # lexical MMR diversity
        div = opts.diversity
        if div and div.get("enabled"):
            hits = mmr(hits, bodies, div.get("lambda", 0.7), fetch, lang)
        if want_coverage:
            hits = _coverage_rerank(store, hits, bodies, qterms, extra_terms, lang)
        return hits

    # Lead-slot rule. The running-share quota cannot ever take slot 1 —
    # (0+1)/(0+1) <= share is false for every share < 1 — so rank 1 gets its
    # own knob. `0` = off. Sign-safe relative margin: scores are negative and
    # ascending-better, so a ratio test would invert across the sign boundary.
    # At margin 1 this reduces to `r0 <= 0` — an unconditional lead.
    lead_margin = _num(opts.lane_lead_margin, 0.0, 0.0, 1.0)
    main = lane(main_rows, "main")
    if lane_share > 0 and reserved_rows:
        reserved = lane(reserved_rows, "reserved")
        main_best, reserved_best = lane_best["main"], lane_best["reserved"]
        lead_first = bool(
            lead_margin > 0 and main_best == main_best and reserved_best == reserved_best and reserved_best - main_best <= lead_margin * abs(main_best)
        )
        hits = interleave_lanes(main, reserved, lane_share, limit, want_source_dedup, lead_first)
    else:
        hits = main[:limit]

    # optional cross-encoder rerank: no-op without an injected reranker
    if opts.rerank and opts.reranker:
        reranked = opts.reranker(query, hits)
        # only a sync reranker can reorder here; keep BM25 order otherwise
        if isinstance(reranked, list):
            hits = reranked

    # parent small-to-big (on by default from the config layer)
    if opts.expand_parent:
        for h in hits:
            pc = h._parent_chunk_id
            if not pc:
                continue
            parent = store.get_chunk_by_id(h.root, pc)
            if parent and parent.chunk_id != h.chunk_id:
                # Collapse to headingPath only: root/path/docType dup the child
                # (same file by construction); display-only, NOT a refetch key.
                h.parent = {"headingPath": parent.heading_path}
    return hits


def search_page(store: SqliteFtsStore, query: str, opts: Optional[SearchOpts] = None, exclusions: Optional[list] = None) -> SearchPage:
    """Run a search and wrap it with what the page is NOT showing.

    The search result page loses rows in THREE layers — the `limit` (which
    counts distinct SOURCES, not sections), the reserved-lane quota, and the
    active exclusions — and the exclusions are the one layer whose effect is
    invisible from the page itself. Every surface that renders a page builds it
    HERE, and therefore carries `total`, `hasMore` and the exclusion list by
    construction."""
    hits = search(store, query, opts)
    total = count_sources(store, query, opts)
    return SearchPage(hits=hits, total=total, has_more=total > len(hits), exclusions=exclusions or [])


def _coverage_rerank(store: SqliteFtsStore, hits: list, bodies: dict, qterms: list, extra_terms: list, lang) -> list:
    """Rerank by IDF-weighted coverage of the ORIGINAL query terms, BM25 as the
    tiebreak. PRF-appended terms count at half weight so expansion can never
    dominate the sort."""
    if not qterms or len(hits) < 2:
        return hits
    all_terms = list(qterms) + list(extra_terms)
    idf = store.idf(all_terms)
    cov: dict = {}
    for h in hits:
        # Folded on both sides: the body may legitimately spell a term with the
        # accents the query omitted.
        toks = set(fold(t) for t in tokenize(f"{h.heading_path} {bodies.get(f'{h.root}\u001f{h.chunk_id}', '')}", lang))
        c = 0.0
        for t in qterms:
            if has_stem(toks, fold(t)):
                c += idf.get(t, 0.0)
        for t in extra_terms:
            if has_stem(toks, fold(t)):
                c += 0.5 * idf.get(t, 0.0)
        cov[h.chunk_id] = c
    return sorted(hits, key=lambda h: (-cov[h.chunk_id], h.score))


def _prf_terms(store: SqliteFtsStore, query: str, qterms: list, first_pass: list, opts: SearchOpts) -> list:
    """RM3-style pseudo-relevance feedback: mine the top candidates of a first
    pass for terms absent from the query and below the corpus-frequency
    ceiling, rank by freq × IDF, return the top `terms`."""
    cfg = opts.prf or {}
    want = max(0, int(cfg.get("terms", 6)))
    top_k = max(1, int(cfg.get("topK", 10)))
    ceiling = min(1.0, max(0.0, float(cfg.get("dfCeiling", 0.1))))
    # RM3 needs a feedback SET. When the first pass returns only a handful of
    # candidates the "top-k relevant" docs are simply the whole corpus, so the
    # mined terms carry no discriminating signal and only dilute the OR-query.
    if not want or len(first_pass) < MIN_FEEDBACK_DOCS:
        return []
    seen = set(qterms)
    freq: dict = {}
    for r in first_pass[:top_k]:
        for t in tokenize(f"{r['headingPath']} {r['body']}", opts.language):
            if t in seen:
                continue
            freq[t] = freq.get(t, 0) + 1
    # Bound the df round trip: only the most frequent feedback candidates.
    cands = [t for t, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:40]]
    if not cands:
        return []
    n = max(1, store.counts()["chunks"])
    df = store.document_frequencies(cands)
    scored = [(t, freq.get(t, 0) * math.log(1 + n / (1 + df.get(t, 0)))) for t in cands if df.get(t, 0) / n <= ceiling]
    scored.sort(key=lambda kv: -kv[1])
    return [t for t, _ in scored[:want]]
