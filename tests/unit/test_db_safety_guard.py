"""P0/1 — set-core must never run a config-supplied DB-mutating command
against a target it cannot prove is disposable.

Companion to `test_integration_pre_build_db_guard.py`, which covers the commands the
*profile* authors. This file covers the other direction: commands the *project config*
hands to set-core (`post_merge_command`, plugin post-merge directives), which run in the
MAIN working tree against the developer's real `DATABASE_URL`.

Mutation check: deleting the `_skip_if_destructive` call in `merger.py` (or the
`target_is_disposable` short-circuit in `db_safety.py`) must fail exactly the blocking
cases below, and leave the must-not-over-block cases green.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch import db_safety  # noqa: E402

PRISMA_PUSH = "npx prisma generate && npx prisma db push --accept-data-loss 2>/dev/null || true"


class _WebLikeProfile:
    """Stand-in for WebProjectType — only the patterns hook matters here."""

    def destructive_db_command_patterns(self):
        return [
            r"\bprisma\b[^|;&]*\bdb\s+push\b",
            r"\bprisma\b[^|;&]*\bmigrate\s+deploy\b",
            r"\bprisma\b[^|;&]*\bdb\s+seed\b",
        ]


def _tree(tmp_path: Path, database_url: str | None) -> str:
    if database_url is not None:
        (tmp_path / ".env").write_text(f'DATABASE_URL="{database_url}"\n')
    return str(tmp_path)


# ─── MUST BLOCK ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("db_url", [
    "postgresql://postgres:postgres@localhost:5432/appdb",
    "mysql://root@localhost:3306/appdb",
    "postgres://user:pw@db.example.com:5432/prod",
])
def test_blocks_prisma_db_push_against_shared_database(tmp_path, db_url):
    """The measured consumer case: db push --accept-data-loss on a prod-copy."""
    reason = db_safety.refuse_db_mutation(
        PRISMA_PUSH, _tree(tmp_path, db_url), context="post_merge_command",
        profile=_WebLikeProfile(),
    )
    assert reason is not None
    assert "not per-worktree-disposable" in reason


def test_blocks_when_env_file_is_missing(tmp_path):
    """No declared target: the command would inherit an ambient DATABASE_URL."""
    assert db_safety.refuse_db_mutation(
        PRISMA_PUSH, _tree(tmp_path, None), profile=_WebLikeProfile(),
    ) is not None


def test_blocks_when_env_has_no_database_url(tmp_path):
    (tmp_path / ".env").write_text("PORT=3000\nAUTH_SECRET=x\n")
    assert db_safety.refuse_db_mutation(
        PRISMA_PUSH, str(tmp_path), profile=_WebLikeProfile(),
    ) is not None


def test_blocks_migrate_deploy_and_seed(tmp_path):
    tree = _tree(tmp_path, "postgresql://localhost:5432/appdb")
    for cmd in ("npx prisma migrate deploy", "pnpm exec prisma db seed"):
        assert db_safety.refuse_db_mutation(
            cmd, tree, profile=_WebLikeProfile(),
        ) is not None, cmd


@pytest.mark.parametrize("cmd", [
    "psql -c 'DROP DATABASE appdb'",
    "psql -c 'TRUNCATE TABLE orders'",
    "npx prisma migrate reset --force",
    "sqlcmd -Q 'DELETE FROM orders'",
])
def test_baseline_patterns_block_without_any_profile(tmp_path, cmd):
    """The Layer-1 backstop must work with NullProfile — no plugin installed."""
    tree = _tree(tmp_path, "postgresql://localhost:5432/appdb")
    assert db_safety.refuse_db_mutation(cmd, tree, profile=None) is not None, cmd


# ─── MUST NOT OVER-BLOCK ────────────────────────────────────────────────────────

def test_allows_db_push_against_disposable_sqlite(tmp_path):
    """`file:` is per-worktree-disposable — the whole point of the exception."""
    assert db_safety.refuse_db_mutation(
        PRISMA_PUSH, _tree(tmp_path, "file:./dev.db"), profile=_WebLikeProfile(),
    ) is None


@pytest.mark.parametrize("cmd", [
    "npx prisma generate",
    "pnpm install --frozen-lockfile",
    "pnpm build",
    "npx tsc --noEmit",
    "node scripts/gen-build-info.mjs",
])
def test_allows_non_destructive_commands_against_shared_database(tmp_path, cmd):
    """Codegen, installs and builds touch no rows — they must keep running."""
    tree = _tree(tmp_path, "postgresql://localhost:5432/appdb")
    assert db_safety.refuse_db_mutation(cmd, tree, profile=_WebLikeProfile()) is None, cmd


def test_empty_command_is_allowed(tmp_path):
    assert db_safety.refuse_db_mutation(
        "", _tree(tmp_path, "postgresql://localhost:5432/appdb"),
    ) is None


def test_profile_without_the_hook_falls_back_to_baseline(tmp_path):
    """An old plugin lacking the hook must not break the guard."""
    class _Old:
        pass

    tree = _tree(tmp_path, "postgresql://localhost:5432/appdb")
    assert db_safety.refuse_db_mutation("npx prisma db push", tree, profile=_Old()) is None
    assert db_safety.refuse_db_mutation("psql -c 'DROP DATABASE x'", tree, profile=_Old()) is not None


def test_url_scheme_never_leaks_credentials():
    assert db_safety.url_scheme("postgresql://user:secret@host/db") == "postgresql"
    assert "secret" not in db_safety.url_scheme("postgresql://user:secret@host/db")


# ─── WIRING: the guard is actually consulted by the merge path ──────────────────

def test_merger_skips_destructive_post_merge_command(tmp_path, monkeypatch):
    """End-to-end at the call site: the command must never reach run_command."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
    from set_orch import merger

    (tmp_path / ".env").write_text('DATABASE_URL="postgresql://localhost:5432/appdb"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(merger, "_load_profile_for_db_safety", lambda: _WebLikeProfile())

    executed = []
    monkeypatch.setattr(
        merger, "run_command",
        lambda *a, **kw: executed.append(a) or merger.CommandResult(0, "", "", 0),
    )

    class _State:
        extras = {"directives": {"post_merge_command": PRISMA_PUSH}}

    monkeypatch.setattr(merger, "load_state", lambda _f: _State())
    merger._post_merge_custom_command("unused-state.json")

    assert executed == [], "destructive post_merge_command reached run_command"


def test_merger_runs_safe_post_merge_command(tmp_path, monkeypatch):
    from set_orch import merger

    (tmp_path / ".env").write_text('DATABASE_URL="postgresql://localhost:5432/appdb"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(merger, "_load_profile_for_db_safety", lambda: _WebLikeProfile())

    executed = []
    monkeypatch.setattr(
        merger, "run_command",
        lambda *a, **kw: executed.append(a) or merger.CommandResult(0, "", "", 0),
    )

    class _State:
        extras = {"directives": {"post_merge_command": "npx prisma generate"}}

    monkeypatch.setattr(merger, "load_state", lambda _f: _State())
    merger._post_merge_custom_command("unused-state.json")

    assert len(executed) == 1, "safe post_merge_command was blocked"


def test_web_profile_supplies_prisma_patterns():
    """The Layer-2 half of the split is actually wired."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "modules" / "web"))
    from set_project_web.project_type import WebProjectType

    patterns = WebProjectType().destructive_db_command_patterns()
    assert patterns, "web profile contributes no patterns"
    assert db_safety.match_destructive_command(
        "npx prisma db push --skip-generate", WebProjectType(),
    )
