"""Common type aliases for set-core.

Centralised here so that mypy can distinguish lineage ids from raw strings
across the codebase without each module re-declaring the NewType.
"""

from __future__ import annotations

import logging
import re
from typing import NewType

logger = logging.getLogger(__name__)


# A normalised, project-relative POSIX-style path identifying a spec lineage.
# Derived from the sentinel's --spec argument.  Wrap raw strings with
# `LineageId("docs/spec.md")` so callers cannot accidentally swap a regular
# str for a lineage id.
LineageId = NewType("LineageId", str)


# Maximum length of a slug we will produce.  Filesystem path segments are
# typically capped at 255 bytes; lineage ids embedded as `<file>-<slug>.json`
# need to leave room for the prefix and the extension.
_SLUG_MAX_LEN = 96

# Characters that are safe inside a single filesystem path segment across
# Linux, macOS and Windows.  Everything else is collapsed to `_`.
_SLUG_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def slug(lineage_id: LineageId | str) -> str:
    """Return a filesystem-safe representation of a lineage id.

    The resulting slug is suitable as a single path segment or as the
    `<slug>` portion of `orchestration-plan-<slug>.json`.

    Rules:
      - Slashes, dots-as-directory-separator, and unicode are collapsed to `_`
      - Leading and trailing separators are stripped
      - The result is lowercased and truncated to `_SLUG_MAX_LEN`
      - Empty input or input that collapses to nothing returns `_unknown`
    """
    if lineage_id is None:
        return "_unknown"
    text = str(lineage_id).strip()
    if not text:
        return "_unknown"
    # Replace any path separator with a hyphen first so we keep the directory
    # boundary visible; subsequent collapsing handles the rest.
    text = text.replace("/", "-").replace("\\", "-")
    cleaned = _SLUG_SAFE_CHARS.sub("_", text)
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return "_unknown"
    cleaned = cleaned.lower()
    if len(cleaned) > _SLUG_MAX_LEN:
        cleaned = cleaned[:_SLUG_MAX_LEN].rstrip("._-") or "_unknown"
    return cleaned


def canonicalise_spec_path(spec_path: str, project_path: str) -> LineageId:
    """Normalise a `--spec` argument into a stable LineageId.

    Absolute and relative paths that refer to the same file resolve to the
    same id.  The id is the project-relative POSIX path of the spec.  When
    the spec lives outside the project tree the absolute POSIX path is
    returned so distinct external specs remain distinguishable.
    """
    if not spec_path:
        raise ValueError("spec_path must be a non-empty string")
    abs_spec = (
        spec_path
        if spec_path.startswith("/")
        else f"{project_path.rstrip('/')}/{spec_path}"
    )
    # Resolve symlinks/.. only for path identity; do NOT require existence
    import os

    try:
        abs_spec_norm = os.path.normpath(os.path.realpath(abs_spec))
    except OSError:
        abs_spec_norm = os.path.normpath(abs_spec)
    abs_proj_norm = os.path.normpath(os.path.realpath(project_path))
    if abs_spec_norm.startswith(abs_proj_norm + os.sep):
        rel = abs_spec_norm[len(abs_proj_norm) + 1 :]
        # POSIX-ify: callers expect forward slashes regardless of host OS.
        rel = rel.replace(os.sep, "/")
        return LineageId(rel)
    # Outside the project tree — keep the absolute path so two different
    # external specs still hash to different ids.
    return LineageId(abs_spec_norm.replace(os.sep, "/"))
