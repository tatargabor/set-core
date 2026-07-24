"""Refuse to author DB-mutating commands against a non-disposable target.

WHY THIS EXISTS (Layer 1, deliberately)
---------------------------------------
`8fae5733` closed one data-loss path: `integration_pre_build` used to run
`prisma db push --accept-data-loss` against whatever `DATABASE_URL` named, and a
worktree's `.env` is a verbatim copy of the project's — routinely a production-data
mirror. That guard lives in the web profile, so it only covers commands the *profile*
authors.

It does not cover the other direction: commands the **project's own config** hands to
set-core, which set-core then executes in the MAIN tree. Measured case (2026-07-24):

    post_merge_command: "npx prisma generate && npx prisma db push --accept-data-loss 2>/dev/null || true"

That runs after every merge, in the main working tree, against the live `DATABASE_URL`,
with stderr discarded and `|| true` swallowing the exit code — so it fails silently and
succeeds destructively. The project's own safety apparatus (a disposable-DB assertion in
its scripts, a PreToolUse firewall) never sees it, because set-core is not going through
the project's scripts — it is running the raw command.

WHY THE BASELINE PATTERNS LIVE HERE AND NOT IN A MODULE
------------------------------------------------------
`.claude/rules/modular-architecture.md` keeps project-type specifics out of
`lib/set_orch/`, and that rule holds for *behaviour* — detection, conventions,
framework patterns. This is not behaviour, it is a **backstop**: the executor of an
arbitrary config-supplied command is Layer 1, so the refusal has to be Layer 1 too. A
safety net that only works when the right plugin happens to be installed is not a safety
net — a project running with `NullProfile` is exactly the project nobody has configured
carefully.

So the split is:
  * Layer 1 here — a small set of *literally* destructive idioms (raw SQL that drops or
    truncates, flags whose own name says "data loss", "migrate reset"). These are not
    web-specific; they are what data loss looks like in any ecosystem.
  * Layer 2 via `ProjectType.destructive_db_command_patterns()` — ecosystem-specific
    additions (a given ORM's schema-push verb, its seed command). Modules extend the
    baseline, they do not replace it.

WHAT "DISPOSABLE" MEANS
-----------------------
Same rule as the shipped guard: only a `file:` URL (per-worktree SQLite) is disposable.
Everything else — postgres, mysql, a remote URL — is shared until per-worktree database
isolation exists. Whether a *named* database is disposable ("ends in `_dev`/`_e2e` and is
on localhost", say) is knowledge the project owns and set-core cannot see, so we do not
guess: we refuse.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Literal data-loss idioms. Kept deliberately short: every entry here must be something
# that destroys rows in ANY ecosystem, so that a false positive is nearly impossible and
# nobody is tempted to weaken the guard to get their pipeline moving.
_BASELINE_DESTRUCTIVE_PATTERNS: tuple[str, ...] = (
    r"--accept-data-loss",          # the flag's own name is the warning
    r"--force-reset",
    r"\bmigrate\s+reset\b",
    r"\bdrop\s+database\b",
    r"\bdrop\s+schema\b",
    r"\btruncate\s+table\b",
    r"\bdelete\s+from\b",
)


def _profile_patterns(profile: Any) -> list[str]:
    """Ecosystem-specific additions from the loaded project type (Layer 2)."""
    if profile is None:
        return []
    getter = getattr(profile, "destructive_db_command_patterns", None)
    if not callable(getter):
        return []
    try:
        patterns = getter() or []
    except Exception:
        logger.debug("destructive_db_command_patterns() raised", exc_info=True)
        return []
    return [p for p in patterns if isinstance(p, str) and p]


def destructive_patterns(profile: Any = None) -> list[str]:
    """Baseline patterns plus whatever the profile contributes."""
    return list(_BASELINE_DESTRUCTIVE_PATTERNS) + _profile_patterns(profile)


def match_destructive_command(command: str, profile: Any = None) -> Optional[str]:
    """Return the first destructive pattern the command matches, else None."""
    if not command:
        return None
    for pattern in destructive_patterns(profile):
        try:
            if re.search(pattern, command, re.IGNORECASE):
                return pattern
        except re.error:
            logger.warning("db_safety: invalid pattern skipped pattern=%s", pattern)
    return None


def read_database_url(tree_path: str) -> str:
    """Read `DATABASE_URL` from `<tree_path>/.env`. Empty string when absent.

    `DATABASE_URL` is a 12-factor convention, not a framework detail — Rails, Django,
    Prisma, Sequelize and plain Go services all read it. Treating it as the target of a
    DB command is therefore Layer-1 knowledge, not web knowledge.
    """
    env_file = os.path.join(tree_path or ".", ".env")
    if not os.path.isfile(env_file):
        return ""
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line.startswith("DATABASE_URL="):
                    continue
                value = line.split("=", 1)[1].strip()
                return value.strip('"').strip("'")
    except OSError as e:
        logger.warning("db_safety: cannot read .env tree=%s error=%s", tree_path, e)
    return ""


def target_is_disposable(db_url: str) -> bool:
    """True only for per-worktree-disposable SQLite (`file:`) targets."""
    return bool(db_url) and db_url.startswith("file:")


def url_scheme(db_url: str) -> str:
    """Scheme prefix for logging — never log the full URL, it carries credentials."""
    if not db_url:
        return "<empty>"
    return db_url.split(":", 1)[0] if ":" in db_url else db_url[:8]


def refuse_db_mutation(
    command: str,
    tree_path: str = ".",
    *,
    context: str = "command",
    profile: Any = None,
) -> Optional[str]:
    """Return a reason string when `command` must NOT run, else None.

    Refuses when the command matches a destructive pattern AND the resolved target is
    not disposable. An absent/empty `DATABASE_URL` also refuses: a destructive command
    with no declared target either picks one up from the ambient environment or fails —
    neither is worth the risk, and the caller loses nothing by skipping.
    """
    pattern = match_destructive_command(command, profile)
    if not pattern:
        return None

    db_url = read_database_url(tree_path)
    if target_is_disposable(db_url):
        return None

    reason = (
        f"refused: {context} matches destructive pattern {pattern!r} and the target is "
        f"not per-worktree-disposable (DATABASE_URL scheme={url_scheme(db_url)})"
    )
    logger.warning(
        "db_safety skip_destructive_command context=%s tree=%s pattern=%s "
        "db_url_scheme=%s command=%s — set-core does not author DB-mutating commands "
        "against a shared target",
        context, tree_path, pattern, url_scheme(db_url), command[:200],
    )
    return reason
