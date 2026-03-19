"""Memory metrics collection, persistence, and reporting.

SQLite-backed storage for hook injection metrics. Data flows:
1. Hooks append per-injection records to session cache (_metrics array)
2. Stop hook flushes session cache to SQLite
3. CLI commands query SQLite for reports and dashboards
"""

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

# --- Paths ---

METRICS_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "set-core", "metrics")
METRICS_DB = os.path.join(METRICS_DIR, "metrics.db")
ENABLED_FLAG = os.path.join(METRICS_DIR, ".enabled")


def is_enabled():
    """Check if metrics collection is enabled."""
    return os.path.exists(ENABLED_FLAG)


def enable():
    """Enable metrics collection."""
    os.makedirs(METRICS_DIR, exist_ok=True)
    Path(ENABLED_FLAG).touch()


def disable():
    """Disable metrics collection."""
    try:
        os.remove(ENABLED_FLAG)
    except FileNotFoundError:
        pass


# --- SQLite Schema ---

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project TEXT,
    started_at TEXT,
    ended_at TEXT,
    total_injections INTEGER,
    total_tokens INTEGER,
    citation_count INTEGER,
    layers_json TEXT,
    injected_id_count INTEGER DEFAULT 0,
    matched_id_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS injections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    ts TEXT,
    layer TEXT,
    event TEXT,
    query TEXT,
    result_count INTEGER,
    filtered_count INTEGER,
    avg_relevance REAL,
    max_relevance REAL,
    min_relevance REAL,
    duration_ms INTEGER,
    token_estimate INTEGER,
    dedup_hit INTEGER,
    context_ids TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    citation_text TEXT,
    citation_type TEXT
);

CREATE TABLE IF NOT EXISTS mem_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    context_id TEXT,
    match_type TEXT,
    UNIQUE(session_id, context_id)
);

CREATE INDEX IF NOT EXISTS idx_injections_session ON injections(session_id);
CREATE INDEX IF NOT EXISTS idx_injections_ts ON injections(ts);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
CREATE INDEX IF NOT EXISTS idx_sessions_ended ON sessions(ended_at);
CREATE INDEX IF NOT EXISTS idx_mem_matches_session ON mem_matches(session_id);
"""

# Columns added after initial schema — migration for existing DBs
_MIGRATIONS = [
    ("injections", "context_ids", "ALTER TABLE injections ADD COLUMN context_ids TEXT DEFAULT '[]'"),
    ("sessions", "injected_id_count", "ALTER TABLE sessions ADD COLUMN injected_id_count INTEGER DEFAULT 0"),
    ("sessions", "matched_id_count", "ALTER TABLE sessions ADD COLUMN matched_id_count INTEGER DEFAULT 0"),
]


def _get_db():
    """Get a SQLite connection, creating schema if needed."""
    os.makedirs(METRICS_DIR, exist_ok=True)
    conn = sqlite3.connect(METRICS_DB, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    # Run column migrations for existing DBs
    for table, column, sql in _MIGRATIONS:
        try:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if column not in cols:
                conn.execute(sql)
                conn.commit()
        except Exception:
            pass
    return conn


# --- Write Operations (called from Stop hook) ---

def flush_session(session_id, project, metrics_records, citations_list=None, mem_matches=None):
    """Flush a session's metrics from cache to SQLite.

    Args:
        session_id: Claude Code session ID
        project: Project name
        metrics_records: List of injection metric dicts from session cache _metrics
        citations_list: Optional list of citation dicts {text, match_type}
        mem_matches: Optional list of passive/explicit match dicts {context_id, match_type}
    """
    if not metrics_records:
        return

    try:
        conn = _get_db()
    except Exception:
        return

    try:
        # Insert injection records
        for rec in metrics_records:
            conn.execute(
                """INSERT INTO injections
                   (session_id, ts, layer, event, query, result_count, filtered_count,
                    avg_relevance, max_relevance, min_relevance,
                    duration_ms, token_estimate, dedup_hit, context_ids)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    rec.get("ts", ""),
                    rec.get("layer", ""),
                    rec.get("event", ""),
                    rec.get("query", "")[:500],
                    rec.get("result_count", 0),
                    rec.get("filtered_count", 0),
                    rec.get("avg_relevance"),
                    rec.get("max_relevance"),
                    rec.get("min_relevance"),
                    rec.get("duration_ms", 0),
                    rec.get("token_estimate", 0),
                    rec.get("dedup_hit", 0),
                    json.dumps(rec.get("context_ids", [])),
                ),
            )

        # Insert legacy citations
        if citations_list:
            for cit in citations_list:
                match_type = cit.get("match_type", cit.get("type", "explicit"))
                conn.execute(
                    "INSERT INTO citations (session_id, citation_text, citation_type) VALUES (?, ?, ?)",
                    (session_id, cit.get("text", "")[:500], match_type),
                )

        # Insert mem_matches (passive + explicit with context_id)
        matched_id_count = 0
        if mem_matches:
            for m in mem_matches:
                cid = m.get("context_id", "")
                if not cid:
                    continue
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO mem_matches (session_id, context_id, match_type) VALUES (?, ?, ?)",
                        (session_id, cid, m.get("match_type", "passive")),
                    )
                    matched_id_count += 1
                except Exception:
                    pass

        # Compute injected_id_count from metrics records
        all_injected_ids = set()
        for rec in metrics_records:
            for cid in rec.get("context_ids", []):
                all_injected_ids.add(cid)
        injected_id_count = len(all_injected_ids)

        # Compute session summary
        timestamps = [r.get("ts", "") for r in metrics_records if r.get("ts")]
        started_at = min(timestamps) if timestamps else ""
        ended_at = datetime.utcnow().isoformat() + "Z"
        total_tokens = sum(r.get("token_estimate", 0) for r in metrics_records)
        citation_count = len(citations_list) if citations_list else 0

        # Per-layer summary
        layers = {}
        for rec in metrics_records:
            layer = rec.get("layer", "unknown")
            if layer not in layers:
                layers[layer] = {"count": 0, "tokens": 0, "relevance_sum": 0.0, "relevance_n": 0}
            layers[layer]["count"] += 1
            layers[layer]["tokens"] += rec.get("token_estimate", 0)
            avg_rel = rec.get("avg_relevance")
            if avg_rel is not None:
                layers[layer]["relevance_sum"] += avg_rel
                layers[layer]["relevance_n"] += 1

        conn.execute(
            """INSERT OR REPLACE INTO sessions
               (id, project, started_at, ended_at, total_injections, total_tokens,
                citation_count, layers_json, injected_id_count, matched_id_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                project,
                started_at,
                ended_at,
                len(metrics_records),
                total_tokens,
                citation_count,
                json.dumps(layers),
                injected_id_count,
                matched_id_count,
            ),
        )

        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# --- Read Operations (called from CLI) ---

def _since_clause(since_days):
    """Build a date cutoff ISO string."""
    cutoff = datetime.utcnow() - timedelta(days=since_days)
    return cutoff.isoformat() + "Z"


def query_report(since_days=7, project=None):
    """Query aggregated metrics for reporting.

    Args:
        since_days: Number of days to look back
        project: Optional project name for prefix filtering (e.g. "sales-raketa"
                 matches "sales-raketa", "sales-raketa-wt-smoke-tests", etc.)

    Returns dict with all data needed for TUI and HTML reports.
    """
    if not os.path.exists(METRICS_DB):
        return None

    try:
        conn = _get_db()
    except Exception:
        return None

    try:
        cutoff = _since_clause(since_days)

        # Build project filter clause and params
        if project:
            proj_clause = " AND s.project LIKE ?"
            proj_param = project + "%"
            # For queries on sessions table directly (no alias)
            sess_clause = " AND project LIKE ?"
        else:
            proj_clause = ""
            proj_param = None
            sess_clause = ""

        def _params(*base):
            """Append project param to base params if filtering."""
            if proj_param:
                return base + (proj_param,)
            return base

        # Session summary
        row = conn.execute(
            f"""SELECT COUNT(*) as cnt, COALESCE(SUM(total_injections),0) as inj,
                      COALESCE(SUM(total_tokens),0) as tok, COALESCE(SUM(citation_count),0) as cit
               FROM sessions s WHERE ended_at >= ?{proj_clause}""",
            _params(cutoff),
        ).fetchone()
        session_count = row["cnt"]
        total_injections = row["inj"]
        total_tokens = row["tok"]
        total_citations = row["cit"]

        if session_count == 0:
            conn.close()
            return None

        # Per-layer breakdown
        layers = conn.execute(
            f"""SELECT layer, COUNT(*) as cnt,
                      COALESCE(AVG(token_estimate),0) as avg_tok,
                      COALESCE(AVG(avg_relevance),0) as avg_rel
               FROM injections i JOIN sessions s ON i.session_id = s.id
               WHERE s.ended_at >= ?{proj_clause}
               GROUP BY layer ORDER BY layer""",
            _params(cutoff),
        ).fetchall()

        # Relevance distribution
        rel_strong = conn.execute(
            f"""SELECT COUNT(*) FROM injections i JOIN sessions s ON i.session_id = s.id
               WHERE s.ended_at >= ? AND avg_relevance >= 0.7 AND dedup_hit = 0{proj_clause}""",
            _params(cutoff),
        ).fetchone()[0]
        rel_partial = conn.execute(
            f"""SELECT COUNT(*) FROM injections i JOIN sessions s ON i.session_id = s.id
               WHERE s.ended_at >= ? AND avg_relevance >= 0.3 AND avg_relevance < 0.7 AND dedup_hit = 0{proj_clause}""",
            _params(cutoff),
        ).fetchone()[0]
        rel_weak = conn.execute(
            f"""SELECT COUNT(*) FROM injections i JOIN sessions s ON i.session_id = s.id
               WHERE s.ended_at >= ? AND avg_relevance < 0.3 AND avg_relevance IS NOT NULL AND dedup_hit = 0{proj_clause}""",
            _params(cutoff),
        ).fetchone()[0]

        # Dedup stats
        dedup_total = conn.execute(
            f"""SELECT COUNT(*) FROM injections i JOIN sessions s ON i.session_id = s.id
               WHERE s.ended_at >= ?{proj_clause}""",
            _params(cutoff),
        ).fetchone()[0]
        dedup_hits = conn.execute(
            f"""SELECT COUNT(*) FROM injections i JOIN sessions s ON i.session_id = s.id
               WHERE s.ended_at >= ? AND dedup_hit = 1{proj_clause}""",
            _params(cutoff),
        ).fetchone()[0]

        # Empty injections (no results, not dedup)
        empty_count = conn.execute(
            f"""SELECT COUNT(*) FROM injections i JOIN sessions s ON i.session_id = s.id
               WHERE s.ended_at >= ? AND filtered_count = 0 AND dedup_hit = 0{proj_clause}""",
            _params(cutoff),
        ).fetchone()[0]

        # Top cited texts
        top_citations = conn.execute(
            f"""SELECT citation_text, COUNT(*) as cnt
               FROM citations c JOIN sessions s ON c.session_id = s.id
               WHERE s.ended_at >= ?{proj_clause}
               GROUP BY citation_text ORDER BY cnt DESC LIMIT 5""",
            _params(cutoff),
        ).fetchall()

        # Daily token burn
        daily_tokens = conn.execute(
            f"""SELECT DATE(s.ended_at) as day, SUM(i.token_estimate) as tok
               FROM injections i JOIN sessions s ON i.session_id = s.id
               WHERE s.ended_at >= ?{proj_clause}
               GROUP BY DATE(s.ended_at) ORDER BY day""",
            _params(cutoff),
        ).fetchall()

        # Per-session detail
        sessions = conn.execute(
            f"""SELECT id, project, started_at, ended_at, total_injections, total_tokens, citation_count
               FROM sessions s WHERE ended_at >= ?{proj_clause} ORDER BY ended_at DESC""",
            _params(cutoff),
        ).fetchall()

        # Daily relevance trend
        daily_relevance = conn.execute(
            f"""SELECT DATE(s.ended_at) as day, AVG(i.avg_relevance) as avg_rel
               FROM injections i JOIN sessions s ON i.session_id = s.id
               WHERE s.ended_at >= ? AND i.avg_relevance IS NOT NULL AND i.dedup_hit = 0{proj_clause}
               GROUP BY DATE(s.ended_at) ORDER BY day""",
            _params(cutoff),
        ).fetchall()

        # Usage rate from context_id tracking
        usage_row = conn.execute(
            f"""SELECT COALESCE(SUM(injected_id_count),0) as inj,
                      COALESCE(SUM(matched_id_count),0) as mat
               FROM sessions s WHERE ended_at >= ?{proj_clause}""",
            _params(cutoff),
        ).fetchone()
        total_injected_ids = usage_row["inj"]
        total_matched_ids = usage_row["mat"]

        # Daily session activity (count + tokens per day)
        daily_sessions = conn.execute(
            f"""SELECT DATE(ended_at) as day, COUNT(*) as cnt, COALESCE(SUM(total_tokens),0) as tok
               FROM sessions s WHERE ended_at >= ?{proj_clause}
               GROUP BY DATE(ended_at) ORDER BY day DESC""",
            _params(cutoff),
        ).fetchall()

        conn.close()

        non_dedup = dedup_total - dedup_hits
        citation_rate = (total_citations / non_dedup * 100) if non_dedup > 0 else 0
        dedup_rate = (dedup_hits / dedup_total * 100) if dedup_total > 0 else 0
        empty_rate = (empty_count / non_dedup * 100) if non_dedup > 0 else 0
        usage_rate = (total_matched_ids / total_injected_ids * 100) if total_injected_ids > 0 else None

        return {
            "since_days": since_days,
            "project": project,
            "session_count": session_count,
            "total_injections": total_injections,
            "total_tokens": total_tokens,
            "total_citations": total_citations,
            "layers": [dict(r) for r in layers],
            "relevance": {
                "strong": rel_strong,
                "partial": rel_partial,
                "weak": rel_weak,
            },
            "dedup_total": dedup_total,
            "dedup_hits": dedup_hits,
            "dedup_rate": round(dedup_rate, 1),
            "citation_rate": round(citation_rate, 1),
            "empty_count": empty_count,
            "empty_rate": round(empty_rate, 1),
            "usage_rate": round(usage_rate, 1) if usage_rate is not None else None,
            "total_injected_ids": total_injected_ids,
            "total_matched_ids": total_matched_ids,
            "top_citations": [{"text": r["citation_text"], "count": r["cnt"]} for r in top_citations],
            "daily_tokens": [{"day": r["day"], "tokens": r["tok"]} for r in daily_tokens],
            "daily_relevance": [{"day": r["day"], "avg_relevance": round(r["avg_rel"], 3)} for r in daily_relevance],
            "sessions": [dict(r) for r in sessions],
            "daily_sessions": [{"day": r["day"], "sessions": r["cnt"], "tokens": r["tok"]} for r in daily_sessions],
        }
    except Exception:
        conn.close()
        return None


def query_session_injections(session_id):
    """Get all injections for a specific session (for drill-down)."""
    if not os.path.exists(METRICS_DB):
        return []
    try:
        conn = _get_db()
        rows = conn.execute(
            """SELECT ts, layer, event, query, result_count, filtered_count,
                      avg_relevance, max_relevance, min_relevance,
                      duration_ms, token_estimate, dedup_hit
               FROM injections WHERE session_id = ? ORDER BY ts""",
            (session_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# --- Citation Scanning ---

CITATION_PATTERNS = [
    "From memory:",
    "from past experience",
    "Based on memory",
    "a memória szerint",
    "From project memory",
    "Based on past",
    "from memory:",
    "From Memory:",
]

# Stopwords for keyword extraction (common English + code terms)
_STOPWORDS = frozenset(
    "the a an is are was were be been being have has had do does did will would "
    "shall should may might can could this that these those it its they them their "
    "we our you your he she his her and or but not no nor for to of in on at by "
    "with from as into about between through during before after above below up "
    "down out off over under again further then once here there when where why how "
    "all each every both few more most other some such only own same so than too "
    "very just don doesn didn won wouldn shouldn couldn wasn weren isn aren hasn "
    "haven hadn mustn needn file code function use used using also new get set run "
    "add added make made see need let".split()
)


def extract_keywords(text, max_keywords=5):
    """Extract significant keywords from memory content for passive matching."""
    import re

    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_-]{2,}", text.lower())
    # Filter stopwords and very short words
    candidates = [w for w in words if w not in _STOPWORDS and len(w) >= 3]
    # Count frequency, prefer less common (more distinctive) words
    freq = {}
    for w in candidates:
        freq[w] = freq.get(w, 0) + 1
    # Sort by frequency (ascending = rarer first), then by length (longer = more specific)
    ranked = sorted(freq.keys(), key=lambda w: (freq[w], -len(w)))
    return ranked[:max_keywords]


def passive_match(injected_content, transcript_path, turn_window=5):
    """Match injected memories against assistant responses via keyword overlap.

    Args:
        injected_content: dict of {context_id: memory_text}
        transcript_path: path to JSONL transcript
        turn_window: max turns after injection to check for matches

    Returns:
        list of {"context_id": str, "match_type": "passive"} dicts
    """
    if not injected_content or not transcript_path or not os.path.exists(transcript_path):
        return []

    # Pre-compute keywords for each injected memory
    mem_keywords = {}
    for cid, content in injected_content.items():
        kws = extract_keywords(content)
        if len(kws) >= 2:
            mem_keywords[cid] = set(kws)

    if not mem_keywords:
        return []

    # Read assistant messages from transcript
    assistant_messages = []
    try:
        with open(transcript_path) as f:
            turn_idx = 0
            for line in f:
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("type") in ("user", "assistant"):
                    turn_idx += 1
                if obj.get("type") != "assistant":
                    continue
                content = obj.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                if texts:
                    assistant_messages.append({
                        "turn": turn_idx,
                        "text": " ".join(texts).lower(),
                    })
    except Exception:
        return []

    # Match: check if 2+ keywords from a memory appear in any assistant message
    # We don't have per-injection turn numbers in the cache, so we check all messages
    # (the turn_window would require injection timestamps which we don't track yet)
    matched = set()
    for cid, kws in mem_keywords.items():
        for msg in assistant_messages:
            overlap = sum(1 for kw in kws if kw in msg["text"])
            if overlap >= 2:
                matched.add(cid)
                break

    return [{"context_id": cid, "match_type": "passive"} for cid in sorted(matched)]


def scan_transcript_citations(transcript_path, session_id=None, injected_content=None):
    """Scan a transcript JSONL for memory citations in assistant messages.

    Returns list of dicts. Legacy explicit citations have {text, match_type: "explicit"}.
    Passive matches (when injected_content provided) have {context_id, match_type: "passive"}.
    """
    results = []
    if not transcript_path or not os.path.exists(transcript_path):
        return results

    # Legacy explicit citation scanning
    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                if obj.get("type") != "assistant":
                    continue

                content = obj.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue

                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "text":
                        continue
                    text = block.get("text", "")
                    for pattern in CITATION_PATTERNS:
                        if pattern in text:
                            idx = text.find(pattern)
                            snippet = text[max(0, idx - 20) : idx + len(pattern) + 80].strip()
                            results.append({"text": snippet, "match_type": "explicit"})
                            break
    except Exception:
        pass

    # Passive matching (when injected content is available)
    if injected_content:
        passive_results = passive_match(injected_content, transcript_path)
        results.extend(passive_results)

    return results


# --- TUI Report Formatting ---

def format_tui_report(data):
    """Format metrics data as a text report for terminal display."""
    if not data:
        return "No metrics data. Enable with: wt-memory metrics --enable"

    lines = []
    lines.append(f"Memory Metrics Report - Last {data['since_days']} days")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Sessions: {data['session_count']:>6}    Injections: {data['total_injections']:>6}    Tokens: {data['total_tokens']:>8}")
    lines.append("")

    # Per-layer breakdown
    lines.append("  BY LAYER")
    lines.append("  " + "-" * 56)
    for layer in data["layers"]:
        avg_rel = layer.get("avg_rel", 0)
        lines.append(
            f"  {layer['layer']:<20} {layer['cnt']:>4}x   {layer['avg_tok']:>6.0f} avg tok   {avg_rel:.2f} avg rel"
        )
    lines.append("")

    # Relevance distribution
    rel = data["relevance"]
    total_rel = rel["strong"] + rel["partial"] + rel["weak"]
    lines.append("  RELEVANCE DISTRIBUTION")
    lines.append("  " + "-" * 56)
    if total_rel > 0:
        s_pct = rel["strong"] / total_rel * 100
        p_pct = rel["partial"] / total_rel * 100
        w_pct = rel["weak"] / total_rel * 100
        s_bar = "#" * int(s_pct / 5)
        p_bar = "#" * int(p_pct / 5)
        w_bar = "#" * int(w_pct / 5)
        lines.append(f"  >0.7 (strong)  {s_bar:<20} {s_pct:>5.1f}%  ({rel['strong']})")
        lines.append(f"  0.3-0.7 (part) {p_bar:<20} {p_pct:>5.1f}%  ({rel['partial']})")
        lines.append(f"  <0.3 (weak)    {w_bar:<20} {w_pct:>5.1f}%  ({rel['weak']})")
    else:
        lines.append("  No relevance data")
    lines.append("")

    # Usage signals
    lines.append("  USAGE SIGNALS")
    lines.append("  " + "-" * 56)
    usage_rate = data.get("usage_rate")
    injected_ids = data.get("total_injected_ids", 0)
    matched_ids = data.get("total_matched_ids", 0)
    if usage_rate is not None:
        lines.append(f"  Usage rate:        {usage_rate:>5.1f}% ({matched_ids}/{injected_ids} memories used)")
    else:
        lines.append(f"  Usage rate:          N/A  (context_id tracking not yet active)")
    lines.append(f"  Citation rate:     {data['citation_rate']:>5.1f}% ({data['total_citations']} explicit citations)")
    lines.append(f"  Dedup hit rate:    {data['dedup_rate']:>5.1f}% ({data['dedup_hits']} saved)")
    lines.append(f"  Empty injections:  {data['empty_rate']:>5.1f}% ({data['empty_count']} empty)")
    lines.append("")

    # Top cited
    if data["top_citations"]:
        lines.append("  TOP CITED MEMORIES")
        lines.append("  " + "-" * 56)
        for i, cit in enumerate(data["top_citations"], 1):
            text = cit["text"][:60]
            lines.append(f"  {i}. \"{text}\"  {cit['count']}x")
        lines.append("")

    return "\n".join(lines)
