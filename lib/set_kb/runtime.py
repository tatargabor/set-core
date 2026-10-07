"""Runtime probe: FTS5 + the `porter unicode61` tokenizer, before anything
else runs.

FTS5 ships enabled in the Python builds set-core meets in practice; where it
does not, the engine STOPS with an error naming the missing piece and the
remediation instead of degrading to an unranked search (there is no fallback —
a grep-shaped fallback is exactly the behaviour this engine exists to replace,
and a silent one would be worse than a loud absence).
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


class KbRuntimeError(RuntimeError):
    """The Python's SQLite lacks a piece the engine requires (FTS5, or the
    `porter unicode61` tokenizer). The message names the piece and the
    remediation."""


def probe() -> dict:
    """Probe the runtime. Returns `{"sqlite": <version string>}` on success;
    raises KbRuntimeError otherwise. Creates no files (probe runs in memory)."""
    conn = sqlite3.connect(":memory:")
    try:
        try:
            conn.execute("CREATE VIRTUAL TABLE probe USING fts5(t, tokenize='porter unicode61')")
            conn.execute("INSERT INTO probe(rowid, t) VALUES(1, 'probe token')")
            conn.execute("SELECT * FROM probe WHERE probe MATCH 'token'").fetchone()
        except sqlite3.OperationalError as e:
            raise KbRuntimeError(
                f"kb engine requires SQLite with the FTS5 extension and the 'porter unicode61' "
                f"tokenizer; this Python's sqlite3 ({sqlite3.sqlite_version}) reported: {e}. "
                f"Remediation: install a Python build that ships FTS5 "
                f"(e.g. `uv python install`, Homebrew python, or python.org installers) — "
                f"the engine does not fall back to an unranked search."
            ) from e
        return {"sqlite": sqlite3.sqlite_version}
    finally:
        conn.close()


def ensure_runtime() -> dict:
    """Probe and raise on failure — the first call on every entry point, BEFORE
    any index path is created (AC: a failing probe creates no index)."""
    info = probe()
    logger.debug("kb runtime ok (SQLite %s)", info["sqlite"])
    return info
