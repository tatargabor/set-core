"""Resolving a stored finding path against the base it was recorded relative to.

A finding stores its file path **relative**, and something else has to say what it is
relative to. Two constraints make it that way, and both were measured rather than assumed:
`Finding.fingerprint()` hashes the ``file`` field, so rewriting the stored value changes a
finding's identity across retries; and ``.claude/review-findings.md`` is committed, so an
absolute ``/home/<user>/…`` inside it publishes the local username and directory layout.

So: **store relative, display absolute**. Artifacts declare a symbolic base (see
``BASE_REPO_ROOT``); display surfaces call :func:`resolve_finding_path` to join it to a
concrete root. This module is the single place that join happens — a second one would be a
second place for the stored and displayed forms to drift apart, silently, in whichever
caller nobody is looking at.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

#: The symbolic base a stored finding path resolves against. Symbolic, not literal: a
#: literal root is an absolute path, which is the thing a committed artifact must not
#: carry, and it goes stale the moment the tree is cloned or moved.
BASE_REPO_ROOT = "repo-root"

#: The field name artifacts use to declare their base.
BASE_FIELD = "path_base"


def resolve_finding_path(file: str, root: str) -> str:
    """Return an absolute, openable path for a stored finding path.

    Args:
        file: The stored path, normally relative to ``root``.
        root: The concrete directory the stored path resolves against.

    Returns:
        The normalized absolute path, or ``""`` when there is nothing to resolve.

    An already-absolute ``file`` is returned normalized and is **not** joined to ``root``.
    An empty ``file`` or an empty ``root`` yields ``""`` rather than a path built from a
    guessed base — a path assembled from the wrong base is worse than no path at all,
    because it looks openable.
    """
    if not file or not str(file).strip():
        return ""
    file = str(file).strip()

    if os.path.isabs(file):
        return os.path.normpath(file)

    if not root or not str(root).strip():
        logger.debug(
            "resolve_finding_path: no root for relative path %r — returning empty "
            "rather than guessing a base", file,
        )
        return ""

    return os.path.normpath(os.path.join(str(root).strip(), file))


def base_of(record: dict) -> str:
    """Return the symbolic base a stored record declares.

    A record written before the base was recorded carries no field. Treating that as an
    error would drop the path from every historical finding — the fail direction that
    loses data — so absence resolves the same way the current default does.
    """
    if not isinstance(record, dict):
        return BASE_REPO_ROOT
    declared = record.get(BASE_FIELD)
    if not declared or not str(declared).strip():
        return BASE_REPO_ROOT
    return str(declared).strip()
