"""Post-merge aggregator: distill ``category-classifications.jsonl`` into
``project-insights.json``.

Run by the orchestrator after every successful change merge. Consumed
by ``category_resolver.resolve_change_categories`` on subsequent
dispatches as deterministic bias AND as Sonnet prompt context.

See ``openspec/specs/project-insights-aggregator/spec.md`` for the
contract this module implements.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter, defaultdict
from typing import Any

logger = logging.getLogger(__name__)


# Tokens we never count toward scope_keyword_categories (too generic).
_SCOPE_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "with", "for", "in", "on",
    "at", "by", "to", "of", "is", "be", "are", "was", "were",
    "this", "that", "these", "those", "it", "its", "as", "from",
    "into", "use", "uses", "using", "via", "etc", "ie", "eg",
})


def _tokenize_scope(scope: str) -> list[str]:
    """Lowercase whitespace tokens, strip punctuation, drop stopwords
    and very short tokens."""
    out: list[str] = []
    for raw in scope.split():
        tok = raw.strip(".,;:!?\"'`()[]{}").lower()
        if len(tok) < 4 or tok in _SCOPE_STOPWORDS:
            continue
        out.append(tok)
    return out


def _read_records(jsonl_path: str) -> list[dict]:
    """Read all valid JSON lines from the audit log. Malformed lines
    are skipped silently — partial corruption shouldn't kill aggregation."""
    if not os.path.isfile(jsonl_path):
        return []
    records: list[dict] = []
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        logger.warning("insights: failed to read %s: %s", jsonl_path, e)
        return []
    return records


def _by_change_type(records: list[dict]) -> dict[str, dict[str, Any]]:
    """Compute per-change-type category statistics.

    For each change_type:
      - category_frequency[cat] = count_with_cat / total_for_change_type
      - common_categories = sorted list where freq >= 0.5
      - rare_categories  = sorted list where 0 < freq < 0.5

    Empty buckets (no records for that change_type) are omitted.
    """
    grouped: dict[str, list[set[str]]] = defaultdict(list)
    for rec in records:
        ct = rec.get("change_type") or ""
        if not ct:
            continue
        # Use FINAL categories (post-LLM union) — that's what was
        # actually injected, not just the deterministic guess.
        final = set(rec.get("final") or [])
        grouped[ct].append(final)

    out: dict[str, dict[str, Any]] = {}
    for ct, cat_lists in grouped.items():
        total = len(cat_lists)
        if total == 0:
            continue
        counter: Counter[str] = Counter()
        for cats in cat_lists:
            counter.update(cats)
        freq = {cat: round(count / total, 3) for cat, count in counter.items()}
        common = sorted(c for c, f in freq.items() if f >= 0.5)
        rare = sorted(c for c, f in freq.items() if 0 < f < 0.5)
        out[ct] = {
            "category_frequency": freq,
            "common_categories": common,
            "rare_categories": rare,
            "samples": total,
        }
    return out


def _by_change_name(records: list[dict]) -> dict[str, list[str]]:
    """Map each change_name to the categories it was last classified
    with. Used by the resolver's ``categories_from_deps`` transitive
    layer (a dependency's categories propagate to dependents)."""
    out: dict[str, list[str]] = {}
    for rec in records:
        name = rec.get("change_name")
        if not name:
            continue
        out[name] = sorted(rec.get("final") or [])
    return out


def _deterministic_vs_llm(records: list[dict]) -> dict[str, Any]:
    """Compute LLM-vs-deterministic agreement telemetry.

    Cache-hit records are excluded — they don't represent fresh model
    output and would inflate agreement artificially.
    """
    fresh = [r for r in records if not r.get("cache_hit")]
    if not fresh:
        return {
            "agreement_rate": None,
            "llm_added_categories": {},
            "samples": 0,
        }
    agree = 0
    added_counter: Counter[str] = Counter()
    for rec in fresh:
        det = set((rec.get("deterministic") or {}).get("categories") or [])
        llm = set((rec.get("llm") or {}).get("categories") or [])
        if det == llm:
            agree += 1
        # Categories the LLM added beyond deterministic
        added_counter.update(llm - det)
    return {
        "agreement_rate": round(agree / len(fresh), 3),
        "llm_added_categories": dict(added_counter),
        "samples": len(fresh),
    }


def _scope_keyword_categories(records: list[dict]) -> dict[str, list[str]]:
    """Map scope tokens to the categories they typically co-occur with.

    Threshold: a token must appear in ≥ 2 distinct changes before it's
    counted (one-off mentions are noise). The per-token categories are
    the union across all changes that used that token.

    The audit log doesn't store the raw scope text per record (only the
    cache_key hash) — so this method reads the deterministic.signals
    and uses change_name as a proxy. For a richer feature set we'd
    persist the scope text in the audit record; out of scope here.
    """
    # NOTE: This requires scope text. The audit record currently
    # stores cache_key (sha256 of scope) but not scope text itself,
    # which means we cannot reconstruct keywords from JSONL alone.
    # We return an empty map for now — once the audit record is
    # extended to include a scope-snippet field (out of scope for
    # this change), this function can be filled in. Documented in
    # `tasks.md` §4.4 as a follow-up.
    return {}


def _uncovered_categories(records: list[dict]) -> dict[str, int]:
    """Count map of categories the LLM proposed that weren't in the
    profile's taxonomy. Persisted as the harvest discovery feed."""
    counter: Counter[str] = Counter()
    for rec in records:
        for cat in (rec.get("uncovered_categories") or []):
            counter[cat] += 1
    return dict(counter)


def update_insights(jsonl_path: str, output_path: str) -> dict[str, Any] | None:
    """Read all classifications from ``jsonl_path``, compute aggregates,
    and atomically write ``project-insights.json`` to ``output_path``.

    Returns the written dict, or None if no records exist (cold start).
    Failures are logged at WARNING and return None — never raises so
    aggregator failure can never block a merge.
    """
    records = _read_records(jsonl_path)
    if not records:
        logger.debug("insights: no records at %s — cold start", jsonl_path)
        return None

    insights = {
        "samples_n": len(records),
        "by_change_type": _by_change_type(records),
        "by_change_name": _by_change_name(records),
        "deterministic_vs_llm": _deterministic_vs_llm(records),
        "scope_keyword_categories": _scope_keyword_categories(records),
        "uncovered_categories": _uncovered_categories(records),
    }

    # Atomic write: write to tmp then rename. ``OSError`` covers both
    # makedirs failure (e.g. parent is a regular file) and write
    # failure (disk full, permissions). Aggregator-level failures must
    # never block the merge; we just log and return None.
    tmp_path = output_path + ".tmp"
    try:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(insights, f, indent=2, sort_keys=True)
        os.replace(tmp_path, output_path)
    except OSError as e:
        logger.warning("insights: write failed: %s", e)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return None

    return insights


def load_insights(output_path: str) -> dict | None:
    """Load ``project-insights.json`` if it exists, else None.

    Used by the resolver to read insights as bias for the deterministic
    layer and as Sonnet prompt context. None signals cold start —
    the resolver runs without bias.
    """
    if not os.path.isfile(output_path):
        return None
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.debug("insights: load failed: %s", e)
        return None
