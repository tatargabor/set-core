"""Per-change category resolver: six deterministic layers + Sonnet additive.

WHY THIS EXISTS
================

Every dispatched change gets review-learning entries injected into its
``input.md``. Until now the filter was ``classify_diff_content(scope)``,
which scans for ``+++/---`` diff markers — but at dispatch time there is
no diff yet, only a scope description. The classifier always returned
``set()``, the consumer treated empty as "include all", and every change
inherited every learning ever recorded for any project.

THE DESIGN
==========

Six layers feed the resolver, all per-change, applied in order:

1. ``categories_from_change_type``    (foundational/feature/...)
2. ``categories_from_requirements``   (REQ-AUTH-* → auth)
3. ``categories_from_paths``          (app/api/ → api)
4. ``detect_scope_categories``        (word-boundary intent regex)
5. ``categories_from_deps``           (transitive closure from insights)
6. ``detect_project_categories``      (FALLBACK only when 1-5 produce ≤ 2 cats)

The five primary layers run unconditionally; layer 6 (project-state
fallback) engages only on thin signal so foundation-shell changes in
huge multi-domain projects don't accidentally inherit every category.

Then a Sonnet 4.6 LLM call ADDITIVELY unions a final layer. The LLM can
add categories the regex layers missed (implicit deps like "checkout
flow" → payment + auth) but cannot remove. Failure modes (timeout,
malformed JSON, API error) gracefully degrade to deterministic-only —
the dispatch never blocks on the LLM.

Every invocation appends one JSON line to
``<project>/.set/state/category-classifications.jsonl`` with the
deterministic + LLM breakdown, agreement diff, and timing/cost
telemetry. The audit log is the cache: a subsequent dispatch with the
same ``cache_key = sha256(scope || sorted(req_ids) || sorted(deps))``
finds the prior result and skips the LLM call.

POST-MERGE FEEDBACK
===================

After each change merges, ``insights.py`` aggregates the audit log into
``project-insights.json`` (per-change-type common categories,
LLM/deterministic agreement rate, scope-keyword frequency, uncovered
categories). The next dispatch's resolver consults the insights as
deterministic bias AND as Sonnet prompt context, creating a virtuous
loop: the system gets smarter about each project's character with every
merged change.

LAYERING (per modular-architecture.md)
======================================

This module owns ORCHESTRATION ONLY — it never branches on project
type. All concrete patterns (file paths, npm package names, scope
keywords, REQ-prefixes) live in profile overrides in
``modules/web/set_project_web/project_type.py`` (and future plugins).

See ``openspec/specs/change-category-resolver/spec.md`` for the
requirement scenarios this implementation must satisfy.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import append_jsonl
from .subprocess_utils import run_claude_logged

logger = logging.getLogger(__name__)


# Threshold: per-change layers 1–5 must produce more than this many
# categories before the project-state fallback (layer 6) is suppressed.
# At ≤ 2, the per-change signal is considered "thin" and we fall back
# to project-wide context.
_FALLBACK_THRESHOLD = 2

# Sonnet call timeout. Per design.md D6: 8 seconds is enough for a
# small-input classification (~1500 input + ~50 output tokens) to
# return at p99, while bounded enough that an outage adds ≤ ~5 % to
# total dispatch time on a 30-change run.
_LLM_TIMEOUT_S = 8


@dataclass
class ResolverResult:
    """Output of ``resolve_change_categories``.

    Fields:
      final_categories: The union of deterministic + LLM, taxonomy-
                        filtered. This is what the dispatcher passes to
                        ``_build_review_learnings(content_categories=…)``.
      deterministic:    Per-layer breakdown of the deterministic union.
                        ``{"categories": set, "signals": {layer_name: set}}``
      llm:              LLM call telemetry. Cache hits → ``cache_hit``.
                        Cache miss with success → categories + reasoning.
                        Failure → ``error`` field present.
      cache_hit:        Whether the LLM result came from JSONL cache.
      delta:            Difference between deterministic and LLM:
                        ``{"added_by_llm": list, "removed_by_llm": list,
                          "agreed": list}``
                        Note: ``removed_by_llm`` is informational —
                        union semantics mean the LLM cannot actually
                        remove categories.
      uncovered_categories: Categories the LLM proposed that aren't in
                            ``profile.category_taxonomy()``. Logged for
                            harvest, NOT injected into learnings.
      audit_record:     JSONL-serializable dict matching design.md D7.
                        The resolver appends this to the audit log;
                        callers don't need to.
    """

    final_categories: set[str]
    deterministic: dict[str, Any]
    llm: dict[str, Any]
    cache_hit: bool
    delta: dict[str, list[str]]
    uncovered_categories: list[str]
    audit_record: dict[str, Any]


# ─── Cache lookup ───────────────────────────────────────────────────────


def _compute_cache_key(scope: str, req_ids: list[str], deps: list[str]) -> str:
    """Deterministic hash of the inputs that determine the LLM response.

    Sorted lists ensure that ``["auth", "api"]`` and ``["api", "auth"]``
    yield the same key — the resolver's output doesn't depend on order.
    """
    payload = json.dumps({
        "scope": scope,
        "req_ids": sorted(req_ids),
        "deps": sorted(deps),
    }, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _lookup_cache(jsonl_path: str, cache_key: str) -> dict | None:
    """Scan the audit log for a prior record with matching cache_key.

    Returns the cached LLM block (categories + reasoning) on hit, or
    None on miss. Reads the file end-to-start so the most recent entry
    wins if the same key was classified multiple times (rare — would
    only happen if cache was invalidated and re-populated).
    """
    if not os.path.isfile(jsonl_path):
        return None
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        logger.debug("cache lookup: failed to read %s", jsonl_path, exc_info=True)
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("cache_key") == cache_key and record.get("llm", {}).get("categories") is not None:
            return record["llm"]
    return None


# ─── LLM invocation ─────────────────────────────────────────────────────


_SYSTEM_PROMPT = """You classify a software change into content categories so the right review-learnings get injected into the implementation agent's prompt.

CATEGORIES YOU MAY USE: {taxonomy}.

Rules:
- Be CONSERVATIVE. Only include a category if THIS specific change clearly involves it.
- Do NOT include categories for the broader project's features that this change doesn't touch.
- The change scope is authoritative. Project pattern is just background context.

PROJECT CONTEXT:
{project_summary}

PROJECT'S PRIOR CLASSIFICATION PATTERNS:
{project_insights}

Respond with JSON only (no prose, no code fences):
{{"categories": ["..."], "confidence": "high|med|low", "reasoning": "one sentence"}}"""


_USER_PROMPT = """change_type: {change_type}
scope: {scope}
assigned requirements: {requirements}
file paths to modify: {paths}
depends_on: {deps}"""


def _build_prompt(
    *,
    scope: str,
    change_type: str,
    req_ids: list[str],
    paths: list[str],
    deps: list[str],
    taxonomy: list[str],
    project_summary: str,
    project_insights_summary: str,
) -> tuple[str, str]:
    """Compose system + user prompts for the LLM call."""
    system = _SYSTEM_PROMPT.format(
        taxonomy=", ".join(taxonomy),
        project_summary=project_summary or "(none provided)",
        project_insights=project_insights_summary or "(no prior runs to summarize)",
    )
    user = _USER_PROMPT.format(
        change_type=change_type or "(unspecified)",
        scope=scope,
        requirements=", ".join(req_ids) if req_ids else "(none)",
        paths=", ".join(paths) if paths else "(none)",
        deps=", ".join(deps) if deps else "(none)",
    )
    return system, user


def _parse_llm_response(raw: str) -> tuple[set[str], dict[str, Any]] | None:
    """Parse Sonnet's JSON response. Returns (categories, metadata) on
    success, None on parse failure."""
    raw = raw.strip()
    # Strip markdown code fences if Sonnet adds them despite the instruction
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[: -3]
        raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    cats = data.get("categories")
    if not isinstance(cats, list):
        return None
    return (
        {c for c in cats if isinstance(c, str)},
        {
            "confidence": str(data.get("confidence", "")),
            "reasoning": str(data.get("reasoning", "")),
        },
    )


def _call_llm(
    profile,
    *,
    scope: str,
    change_type: str,
    req_ids: list[str],
    paths: list[str],
    deps: list[str],
    project_path: Path,
    project_insights_summary: str,
) -> tuple[set[str], dict[str, Any]]:
    """Invoke the profile's classifier model.

    Returns ``(categories, metadata)`` on success or ``(set(), {"error": …})``
    on any failure (timeout, parse error, API error). Never raises.

    Per design.md D3, this is the ADDITIVE LLM layer — its return value
    will be unioned with the deterministic union, never used to remove.
    """
    model = getattr(profile, "llm_classifier_model", None)
    if not model:
        return set(), {"skipped": "model_disabled"}

    taxonomy = profile.category_taxonomy() or ["general"]
    project_summary = profile.project_summary_for_classifier(project_path) or ""

    system, user = _build_prompt(
        scope=scope,
        change_type=change_type,
        req_ids=req_ids,
        paths=paths,
        deps=deps,
        taxonomy=taxonomy,
        project_summary=project_summary,
        project_insights_summary=project_insights_summary,
    )

    # Compose a single prompt for run_claude_logged (the helper takes
    # one prompt string and tags it with [PURPOSE:…]). System and user
    # are concatenated; the LLM treats the SYSTEM block as preamble.
    full_prompt = f"{system}\n\n---\n\n{user}"

    started = time.monotonic()
    try:
        result = run_claude_logged(
            full_prompt,
            purpose="classify_categories",
            timeout=_LLM_TIMEOUT_S,
            model=model,
            extra_args=["--max-turns", "1"],
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "category_resolver: LLM call raised %s — falling back to deterministic",
            type(e).__name__,
        )
        return set(), {
            "model": model,
            "error": f"{type(e).__name__}: {e}",
            "duration_ms": duration_ms,
        }

    duration_ms = int((time.monotonic() - started) * 1000)

    if result.timed_out:
        return set(), {
            "model": model,
            "error": "timeout",
            "duration_ms": duration_ms,
        }

    if result.exit_code != 0:
        return set(), {
            "model": model,
            "error": f"exit_code_{result.exit_code}",
            "duration_ms": duration_ms,
            "stderr": (result.stderr or "")[: 500],
        }

    parsed = _parse_llm_response(result.stdout or "")
    if parsed is None:
        return set(), {
            "model": model,
            "error": "json_parse",
            "duration_ms": duration_ms,
            "raw": (result.stdout or "")[: 500],
        }

    cats, meta = parsed
    return cats, {
        "model": model,
        "duration_ms": duration_ms,
        "cost_usd": float(getattr(result, "cost_usd", 0.0) or 0.0),
        "input_tokens": int(getattr(result, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(result, "output_tokens", 0) or 0),
        **meta,
    }


# ─── Insights summary ───────────────────────────────────────────────────


def _summarize_insights(insights: dict | None, change_type: str) -> str:
    """Build a one-paragraph summary of project insights for the LLM
    prompt. Returns empty string when insights are unavailable (cold
    start) so the prompt template substitutes a clear placeholder."""
    if not insights:
        return ""
    lines: list[str] = []
    by_type = (insights.get("by_change_type") or {}).get(change_type) or {}
    common = by_type.get("common_categories") or []
    rare = by_type.get("rare_categories") or []
    if common:
        lines.append(
            f"This project's prior {change_type} changes commonly involve: {', '.join(common)}."
        )
    if rare:
        lines.append(f"Rare for {change_type}: {', '.join(rare)}.")
    return " ".join(lines) if lines else ""


def _insights_layer_categories(insights: dict | None, change_type: str) -> set[str]:
    """Return the categories common for this change_type per insights —
    used as deterministic bias before per-change layers run."""
    if not insights:
        return set()
    by_type = (insights.get("by_change_type") or {}).get(change_type) or {}
    return set(by_type.get("common_categories") or [])


# ─── Audit record ───────────────────────────────────────────────────────


def _build_audit_record(
    *,
    change_name: str,
    cache_key: str,
    cache_hit: bool,
    change_type: str,
    deterministic_cats: set[str],
    layer_signals: dict[str, set[str]],
    llm_cats: set[str],
    llm_meta: dict[str, Any],
    final_cats: set[str],
    uncovered: list[str],
) -> dict[str, Any]:
    """Schema documented in design.md D7."""
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "change_name": change_name,
        "cache_key": cache_key,
        "cache_hit": cache_hit,
        "change_type": change_type,
        "deterministic": {
            "categories": sorted(deterministic_cats),
            "signals": {k: sorted(v) for k, v in layer_signals.items()},
        },
        "llm": {
            "categories": sorted(llm_cats) if llm_cats or "error" not in llm_meta else None,
            **llm_meta,
        },
        "final": sorted(final_cats),
        "delta": {
            "added_by_llm": sorted(llm_cats - deterministic_cats),
            "agreed": sorted(llm_cats & deterministic_cats),
            "removed_by_llm": sorted(deterministic_cats - llm_cats),
        },
        "uncovered_categories": sorted(uncovered),
    }


# ─── Main entry point ───────────────────────────────────────────────────


def resolve_change_categories(
    *,
    change_name: str,
    change_type: str,
    scope: str,
    req_ids: list[str],
    manifest_paths: list[str],
    deps: list[str],
    profile,
    project_path: Path,
    audit_log_path: str,
    project_insights: dict | None = None,
) -> ResolverResult:
    """Resolve content categories for one change.

    Required keyword arguments:
      change_name:      Used in the audit record; never affects classification.
      change_type:      Phase string (foundational/feature/...).
      scope:            Free-form scope description.
      req_ids:          Assigned requirement IDs (e.g. ["REQ-AUTH-001"]).
      manifest_paths:   File paths the change is expected to touch
                        (extracted from scope by the manifest extractor).
      deps:             ``change.depends_on`` list (parent change names).
      profile:          The active ``ProjectType`` (consulted for all
                        category hooks).
      project_path:     Path to project root (for state-based detection).
      audit_log_path:   Where to append the audit record. Pass
                        ``LineagePaths.category_classifications``.

    Optional:
      project_insights: Already-loaded ``project-insights.json`` dict, or
                        None to skip the bias step.

    Returns a ``ResolverResult`` whose ``final_categories`` is what the
    dispatcher should pass to ``_build_review_learnings``. The audit
    record is already appended to the JSONL — the caller doesn't need
    to write it.

    Never raises — failures degrade gracefully to deterministic-only.
    """
    # ── Layers 1–5: per-change deterministic detection ─────────────────
    layer_signals: dict[str, set[str]] = {}

    layer_signals["change_type"] = profile.categories_from_change_type(change_type) or set()
    layer_signals["requirements"] = profile.categories_from_requirements(req_ids) or set()
    layer_signals["paths"] = profile.categories_from_paths(manifest_paths) or set()
    layer_signals["scope"] = profile.detect_scope_categories(scope) or set()

    # Layer 5: depends_on transitive closure via insights.
    # Each parent change_name is looked up in insights' historical
    # records — if a parent classified as auth, this change inherits
    # auth as a possible signal.
    deps_cats: set[str] = set()
    if project_insights and deps:
        deps_history = project_insights.get("by_change_name") or {}
        for dep_name in deps:
            for cat in (deps_history.get(dep_name) or []):
                deps_cats.add(cat)
    layer_signals["deps"] = deps_cats

    # Insights bias — common categories for THIS change_type from prior
    # successful classifications. Layered alongside change_type defaults.
    insights_bias = _insights_layer_categories(project_insights, change_type)
    layer_signals["insights"] = insights_bias

    primary_union = (
        layer_signals["change_type"]
        | layer_signals["requirements"]
        | layer_signals["paths"]
        | layer_signals["scope"]
        | layer_signals["deps"]
        | layer_signals["insights"]
        | {"general"}
    )

    # Layer 6: project-state FALLBACK — only when primary signal is thin.
    if len(primary_union) <= _FALLBACK_THRESHOLD + 1:  # +1 because `general` is always in
        layer_signals["project_state"] = profile.detect_project_categories(project_path) or set()
    else:
        layer_signals["project_state"] = set()

    deterministic_cats = primary_union | layer_signals["project_state"]

    # ── Cache lookup ───────────────────────────────────────────────────
    cache_key = _compute_cache_key(scope, req_ids, deps)
    cached = _lookup_cache(audit_log_path, cache_key)

    if cached is not None:
        # Cache hit — reuse prior LLM result.
        llm_cats = set(cached.get("categories") or [])
        llm_meta = {k: v for k, v in cached.items() if k != "categories"}
        cache_hit = True
    else:
        # Cache miss — invoke the LLM.
        insights_summary = _summarize_insights(project_insights, change_type)
        llm_cats, llm_meta = _call_llm(
            profile,
            scope=scope,
            change_type=change_type,
            req_ids=req_ids,
            paths=manifest_paths,
            deps=deps,
            project_path=project_path,
            project_insights_summary=insights_summary,
        )
        cache_hit = False

    # ── Taxonomy filtering ─────────────────────────────────────────────
    taxonomy = set(profile.category_taxonomy() or ["general"])
    uncovered = sorted(llm_cats - taxonomy)
    llm_cats_filtered = llm_cats & taxonomy

    # ── Final union (LLM additive) ─────────────────────────────────────
    final_cats = deterministic_cats | llm_cats_filtered

    # ── Audit record + persistence ─────────────────────────────────────
    audit_record = _build_audit_record(
        change_name=change_name,
        cache_key=cache_key,
        cache_hit=cache_hit,
        change_type=change_type,
        deterministic_cats=deterministic_cats,
        layer_signals=layer_signals,
        llm_cats=llm_cats_filtered,
        llm_meta=llm_meta,
        final_cats=final_cats,
        uncovered=uncovered,
    )

    try:
        append_jsonl(audit_log_path, audit_record)
    except OSError as e:
        logger.warning("category_resolver: audit append failed: %s", e)

    return ResolverResult(
        final_categories=final_cats,
        deterministic={
            "categories": sorted(deterministic_cats),
            "signals": {k: sorted(v) for k, v in layer_signals.items()},
        },
        llm={"categories": sorted(llm_cats_filtered), **llm_meta} if not cache_hit else {
            "categories": sorted(llm_cats_filtered), "cache_hit": True, **llm_meta
        },
        cache_hit=cache_hit,
        delta={
            "added_by_llm": sorted(llm_cats_filtered - deterministic_cats),
            "agreed": sorted(llm_cats_filtered & deterministic_cats),
            "removed_by_llm": sorted(deterministic_cats - llm_cats_filtered),
        },
        uncovered_categories=uncovered,
        audit_record=audit_record,
    )
