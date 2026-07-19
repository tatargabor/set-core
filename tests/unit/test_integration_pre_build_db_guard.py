"""Tests for the integration_pre_build DB-mutation guard (final-plan Phase 0).

Background — the defect this guard closes:

`integration_pre_build()` ran `prisma db push --skip-generate --accept-data-loss`
with `PRISMA_USER_CONSENT_FOR_DANGEROUS_AI_ACTION=true`, and its ONLY precondition
was that `prisma/schema.prisma` exists. A worktree's `.env` is a verbatim copy of
the project's `.env`, so DATABASE_URL is whatever the developer points at — on a
real consumer that is routinely a production-data mirror. The command is authored
by the framework itself, so a project's own disposable-DB guards never see it.

The twin path `e2e_pre_gate()` already had a `file:` check. It was never copied
here. These tests exist so it cannot be silently removed again — a data-loss
guard with no test is exactly the silent-regression class this repo keeps hitting.

Note `prisma migrate deploy` is NOT an acceptable substitute for the skip: it
applies the branch's pending migrations to whatever DATABASE_URL names, and those
migrations routinely contain DROP COLUMN / ALTER TYPE. Hence: skip, do not
substitute.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"))

from set_project_web.project_type import WebProjectType


SCHEMA_POSTGRES = """
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
"""

SCHEMA_SQLITE = """
datasource db {
  provider = "sqlite"
  url      = env("DATABASE_URL")
}
"""


def _make_worktree(tmpdir: str, schema: str, env_body: str | None) -> str:
    """Create a minimal worktree with a prisma schema and optional .env."""
    wt = Path(tmpdir)
    (wt / "prisma").mkdir(parents=True, exist_ok=True)
    (wt / "prisma" / "schema.prisma").write_text(schema)
    if env_body is not None:
        (wt / ".env").write_text(env_body)
    return str(wt)


def _run_pre_build(wt_path: str):
    """Run integration_pre_build with subprocess.run patched. Returns (result, commands)."""
    commands: list[list[str]] = []

    def _fake_run(cmd, *args, **kwargs):
        commands.append(list(cmd))
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""
        return proc

    with patch("set_project_web.project_type.subprocess.run", side_effect=_fake_run):
        result = WebProjectType().integration_pre_build(wt_path)
    return result, commands


def _is_db_push(cmd: list[str]) -> bool:
    return "prisma" in cmd and "push" in cmd


def _is_generate(cmd: list[str]) -> bool:
    return "prisma" in cmd and "generate" in cmd


def _is_migrate(cmd: list[str]) -> bool:
    return "prisma" in cmd and "migrate" in cmd


# --- the guard must BLOCK -----------------------------------------------------

def test_postgres_target_is_never_pushed_to():
    """The live-data case: a postgres DATABASE_URL must not receive db push."""
    with tempfile.TemporaryDirectory() as tmp:
        wt = _make_worktree(
            tmp, SCHEMA_POSTGRES,
            'DATABASE_URL="postgresql://postgres:postgres@localhost:5432/appdb"\n',
        )
        result, commands = _run_pre_build(wt)

    assert result is True, "guard must not fail the gate — it skips the sync"
    assert not any(_is_db_push(c) for c in commands), (
        f"db push MUST NOT run against a postgres target; commands were {commands}"
    )


def test_mysql_target_is_never_pushed_to():
    """Any non-file: provider is treated as shared, not just postgres."""
    with tempfile.TemporaryDirectory() as tmp:
        wt = _make_worktree(
            tmp, SCHEMA_POSTGRES,
            'DATABASE_URL="mysql://root@localhost:3306/appdb"\n',
        )
        result, commands = _run_pre_build(wt)

    assert result is True
    assert not any(_is_db_push(c) for c in commands)


def test_missing_env_file_does_not_push():
    """No .env at all → no known target → must not push (guard on empty)."""
    with tempfile.TemporaryDirectory() as tmp:
        wt = _make_worktree(tmp, SCHEMA_POSTGRES, None)
        result, commands = _run_pre_build(wt)

    assert result is True
    assert not any(_is_db_push(c) for c in commands)


def test_env_without_database_url_does_not_push():
    """.env present but no DATABASE_URL → still no target → must not push."""
    with tempfile.TemporaryDirectory() as tmp:
        wt = _make_worktree(tmp, SCHEMA_POSTGRES, 'PORT=3000\n')
        result, commands = _run_pre_build(wt)

    assert result is True
    assert not any(_is_db_push(c) for c in commands)


def test_guard_never_substitutes_migrate_deploy():
    """Skipping must mean skipping — migrate deploy also mutates the target."""
    with tempfile.TemporaryDirectory() as tmp:
        wt = _make_worktree(
            tmp, SCHEMA_POSTGRES,
            'DATABASE_URL="postgresql://postgres:postgres@localhost:5432/appdb"\n',
        )
        _, commands = _run_pre_build(wt)

    assert not any(_is_migrate(c) for c in commands), (
        f"migrate deploy is not a safe fallback; commands were {commands}"
    )


# --- the guard must NOT over-block --------------------------------------------

def test_sqlite_target_still_gets_schema_sync():
    """file: targets are per-worktree-disposable — they must keep working."""
    with tempfile.TemporaryDirectory() as tmp:
        wt = _make_worktree(tmp, SCHEMA_SQLITE, 'DATABASE_URL="file:./dev.db"\n')
        result, commands = _run_pre_build(wt)

    assert result is True
    assert any(_is_db_push(c) for c in commands), (
        f"SQLite worktrees must still get db push; commands were {commands}"
    )


def test_prisma_generate_always_runs():
    """generate emits client code and touches no rows — it must not be skipped.

    The build gate imports @prisma/client, so skipping generate would turn a
    data-safety fix into a build breakage.
    """
    with tempfile.TemporaryDirectory() as tmp:
        wt = _make_worktree(
            tmp, SCHEMA_POSTGRES,
            'DATABASE_URL="postgresql://postgres:postgres@localhost:5432/appdb"\n',
        )
        _, commands = _run_pre_build(wt)

    assert any(_is_generate(c) for c in commands), (
        f"prisma generate must run even when the DB sync is skipped; got {commands}"
    )


def test_no_schema_is_still_a_noop():
    """Unchanged behaviour: no prisma schema → nothing runs at all."""
    with tempfile.TemporaryDirectory() as tmp:
        result, commands = _run_pre_build(tmp)

    assert result is True
    assert commands == []
