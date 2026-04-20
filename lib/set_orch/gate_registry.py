"""Content-aware gate selection (section 7 of
fix-replan-stuck-gate-and-decomposer).

Layer 1 module. Provides:

- `classify_content(globs, rules)` — match file-glob hints against a
  profile's `content_classifier_rules()` and return the set of content
  tags (ui, e2e_ui, server, schema, config, i18n_catalog, …).
- `tags_to_gates(tags, mapping)` — translate a tag set to a gate-name
  set via the profile's `content_tag_to_gates()` map.
- `augment_gate_config_with_content(gc, change, profile)` — additive
  union of content-driven gate names into an existing `GateConfig`. The
  function never removes gates; `gate_hints` "skip"/"require" still
  override the content scan (require always wins, skip always wins).
- `redetect(change, committed_files, profile)` — read the first commit's
  diff files, reclassify, and emit `GATE_SET_EXPANDED` when the set
  grows. The engine calls this on the first-commit transition.

The existing public `GateConfig` type lives in `gate_profiles.py` and is
re-exported here so callers can import from either module while the
internals migrate.
"""
from __future__ import annotations

import fnmatch
import logging
import re
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


# Back-compat re-export: the `GateConfig` + `resolve_gate_config` public
# surface lives in gate_profiles.py; expose it here so future code can
# import from the new module without churning every existing call site.
from .gate_profiles import (  # noqa: F401,E402
    GateConfig,
    UNIVERSAL_DEFAULTS,
    resolve_gate_config,
)


_GLOB_CACHE: dict[str, re.Pattern[str]] = {}


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a bash-style glob (with `**`) to a regex.

    `**` matches any number of path segments (including zero). `*` matches
    a single segment. Lone `?` matches one character (non-separator).
    Cached so repeated calls are cheap.
    """
    if pattern in _GLOB_CACHE:
        return _GLOB_CACHE[pattern]
    # Split on `**/` first so each side is translated separately.
    tokens = pattern.replace("**", "__DOUBLESTAR__")
    escaped = re.escape(tokens)
    # Translate escaped markers back into regex
    regex = (
        escaped
        .replace(r"__DOUBLESTAR__/", r"(?:.*/)?")
        .replace(r"__DOUBLESTAR__", r".*")
        .replace(r"\*", r"[^/]*")
        .replace(r"\?", r"[^/]")
    )
    compiled = re.compile(rf"^{regex}$")
    _GLOB_CACHE[pattern] = compiled
    return compiled


def _match_globs(path: str, globs: Iterable[str]) -> bool:
    """Return True if `path` matches any of `globs`.

    Handles `**` (recursive) and `*` (single segment) correctly, unlike
    the stdlib `fnmatch` which treats `**` as a double-splat on everything.
    """
    for g in globs or []:
        if _glob_to_regex(g).match(path):
            return True
    return False


def classify_content(
    paths: Iterable[str],
    rules: dict[str, list[str]],
) -> set[str]:
    """Return the set of content tags matched by `paths` against `rules`.

    `rules` is the mapping from `ProjectType.content_classifier_rules()`
    — `{tag: [glob, …]}`. A tag is included when ANY of its globs matches
    at least one path.

    Empty `paths` or empty `rules` → empty set (no content hints).
    """
    tags: set[str] = set()
    paths_list = [p for p in paths or [] if p]
    if not paths_list or not rules:
        return tags
    for tag, globs in rules.items():
        for path in paths_list:
            if _match_globs(path, globs):
                tags.add(tag)
                break
    return tags


def tags_to_gates(
    tags: Iterable[str],
    tag_to_gate_map: dict[str, set[str]],
) -> set[str]:
    """Flatten a tag set to the union of gate names it maps to."""
    out: set[str] = set()
    for tag in tags or []:
        out |= set(tag_to_gate_map.get(tag, set()))
    return out


def augment_gate_config_with_content(
    gc: "GateConfig",
    change,
    profile=None,
) -> set[str]:
    """Additively union content-driven gate names into `gc`.

    Honors `gate_hints` on the change (require/skip) — "require" always
    forces inclusion, "skip" always excludes. The content scan can only
    ADD gates, never remove. Returns the set of gate names added.

    Safe to call on profiles without classifier rules — returns empty.
    """
    if profile is None:
        return set()
    rules = {}
    tag_map = {}
    try:
        rules = profile.content_classifier_rules() or {}
        tag_map = profile.content_tag_to_gates() or {}
    except Exception:
        logger.debug("profile classifier rules unavailable", exc_info=True)
        return set()

    paths = list(getattr(change, "touched_file_globs", []) or [])
    tags = classify_content(paths, rules) if paths else set()
    suggested_gates = tags_to_gates(tags, tag_map)

    # Apply hints: require wins, skip wins.
    hints = getattr(change, "gate_hints", None) or {}
    for g in list(suggested_gates):
        if hints.get(g) == "skip":
            suggested_gates.discard(g)

    added: set[str] = set()
    for g in suggested_gates:
        # Only add if currently not runnable (skipped or missing).
        if not gc.should_run(g):
            gc.set(g, "run")
            added.add(g)

    # gate_hints="require" forces run even if not suggested by content.
    for g, mode in hints.items():
        if mode == "require" and not gc.should_run(g):
            gc.set(g, "run")
            added.add(g)

    if added:
        logger.info(
            "Content-aware gate selector: added %s to %s (tags=%s)",
            sorted(added), getattr(change, "name", "?"), sorted(tags),
        )
    return added


def redetect(
    change,
    committed_file_paths: Iterable[str],
    profile=None,
) -> set[str]:
    """Re-run content classification on the first commit's file list.

    Called once per change on the transition from
    `new_commits_since_dispatch == 0 → 1` (engine monitor loop). Unions
    the newly-detected tags' file globs into `change.touched_file_globs`
    and returns the set of gate names added.

    The caller is responsible for emitting `GATE_SET_EXPANDED` and
    re-running the verify pipeline.
    """
    paths = list(committed_file_paths or [])
    if not paths:
        return set()

    rules = {}
    tag_map = {}
    try:
        if profile is not None:
            rules = profile.content_classifier_rules() or {}
            tag_map = profile.content_tag_to_gates() or {}
    except Exception:
        return set()

    tags = classify_content(paths, rules)
    added_gates = tags_to_gates(tags, tag_map)

    # Union committed paths into the change's touched_file_globs so the
    # next gate-selector run sees the expanded scope.
    existing = set(getattr(change, "touched_file_globs", []) or [])
    for p in paths:
        existing.add(p)
    try:
        change.touched_file_globs = sorted(existing)
    except AttributeError:
        # Old state snapshots without the field — silently skip.
        logger.debug("change %s lacks touched_file_globs attr", getattr(change, "name", "?"))

    return added_gates
