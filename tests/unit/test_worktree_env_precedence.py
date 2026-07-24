"""P0/2 — the project's worktree-init hook wins over config `env_vars`.

`set-new` runs `set/hooks/worktree-init.sh` at creation time; that hook is what makes a
worktree independent (its own port base, its own database name derived from the change
id). The dispatcher then applied config `env_vars` on top — restoring the SHARED
DATABASE_URL and silently undoing the isolation.

Two behaviours are locked down here:
  1. `.env` is edited line-wise, so comments and unrelated lines survive.
  2. the hook is re-run after `env_vars`, so its per-tree decisions have the last word.

Mutation check: removing the `_rerun_project_worktree_init` call fails the precedence
tests; reverting `_apply_env_vars_to_env_file` to a whole-file rewrite fails the
comment-preservation tests.
"""

import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))

from set_orch.dispatcher import (  # noqa: E402
    _apply_env_vars_to_env_file,
    _rerun_project_worktree_init,
)


# ─── .env is edited, not rewritten ──────────────────────────────────────────────

def test_replaces_value_in_place_and_keeps_comments(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# Secrets — do not commit\n"
        'AUTH_SECRET="keep-me"\n'
        "\n"
        "# the main tree's, replaced by worktree-init\n"
        '# DATABASE_URL="postgresql://localhost:5432/app"\n'
        'DATABASE_URL="postgresql://localhost:5432/app_mychange"\n'
    )

    _apply_env_vars_to_env_file(str(env), {"DATABASE_URL": "postgresql://localhost:5432/app"})
    out = env.read_text()

    assert "# Secrets — do not commit" in out, "comments were dropped"
    assert '# DATABASE_URL="postgresql://localhost:5432/app"' in out, "commented line lost"
    assert 'AUTH_SECRET="keep-me"' in out, "unrelated key lost"
    assert out.count("\nDATABASE_URL=") + out.startswith("DATABASE_URL=") == 1, \
        "DATABASE_URL duplicated instead of replaced"


def test_appends_keys_that_are_absent(tmp_path):
    env = tmp_path / ".env"
    env.write_text('AUTH_SECRET="x"\n')
    _apply_env_vars_to_env_file(str(env), {"NEW_KEY": "value"})
    assert 'NEW_KEY="value"' in env.read_text()
    assert 'AUTH_SECRET="x"' in env.read_text()


def test_creates_file_when_missing(tmp_path):
    env = tmp_path / ".env"
    _apply_env_vars_to_env_file(str(env), {"A": "1"})
    assert env.read_text() == 'A="1"\n'


def test_does_not_double_quote_already_quoted_values(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=old\n")
    _apply_env_vars_to_env_file(str(env), {"A": '"already"'})
    assert env.read_text().strip() == 'A="already"'


def test_commented_assignment_is_not_treated_as_the_key(tmp_path):
    """`# DATABASE_URL=...` must not absorb the replacement."""
    env = tmp_path / ".env"
    env.write_text('# DATABASE_URL="old"\n')
    _apply_env_vars_to_env_file(str(env), {"DATABASE_URL": "new"})
    out = env.read_text()
    assert '# DATABASE_URL="old"' in out
    assert 'DATABASE_URL="new"' in out.replace('# DATABASE_URL="old"', "")


# ─── the hook runs last and wins ────────────────────────────────────────────────

def _install_hook(wt: Path, body: str) -> Path:
    hook = wt / "set" / "hooks" / "worktree-init.sh"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(body)
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC | stat.S_IRWXU)
    return hook


def test_hook_reruns_and_overrides_env_vars(tmp_path):
    """The end state must be the hook's value, not the config's."""
    wt = tmp_path / "wt"
    wt.mkdir()
    env = wt / ".env"
    env.write_text('DATABASE_URL="postgresql://localhost:5432/app_mychange"\n')

    _install_hook(wt, """#!/usr/bin/env bash
set -e
# Mirrors the real contract: only rewrite when the value still equals main's.
if grep -q 'app_mychange' "$2/.env"; then exit 0; fi
sed -i 's#/app"#/app_mychange"#' "$2/.env"
""")

    # config env_vars drag it back to the shared database …
    _apply_env_vars_to_env_file(str(env), {"DATABASE_URL": "postgresql://localhost:5432/app"})
    assert "app_mychange" not in env.read_text()

    # … and the hook takes it back.
    _rerun_project_worktree_init(str(tmp_path), str(wt), "mychange")
    assert 'DATABASE_URL="postgresql://localhost:5432/app_mychange"' in env.read_text()


def test_hook_receives_contract_arguments(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    _install_hook(wt, '#!/usr/bin/env bash\nprintf "%s|%s|%s" "$1" "$2" "$3" > "$2/argv.txt"\n')

    _rerun_project_worktree_init(str(tmp_path), str(wt), "my-change-id")

    assert (wt / "argv.txt").read_text() == f"{tmp_path}|{wt}|my-change-id"


def test_missing_hook_is_a_no_op(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    _rerun_project_worktree_init(str(tmp_path), str(wt), "c")  # must not raise


def test_non_executable_hook_is_skipped_not_executed(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    hook = wt / "set" / "hooks" / "worktree-init.sh"
    hook.parent.mkdir(parents=True)
    hook.write_text('#!/usr/bin/env bash\ntouch "$2/RAN"\n')
    hook.chmod(0o644)

    _rerun_project_worktree_init(str(tmp_path), str(wt), "c")
    assert not (wt / "RAN").exists()


def test_failing_hook_is_non_fatal(tmp_path):
    wt = tmp_path / "wt"
    wt.mkdir()
    _install_hook(wt, '#!/usr/bin/env bash\necho boom >&2\nexit 3\n')
    _rerun_project_worktree_init(str(tmp_path), str(wt), "c")  # must not raise


# ─── ordering is the bug; assert the wiring, not just the helpers ───────────────

def test_dispatch_reruns_hook_after_applying_env_vars():
    """The defect was ORDER: env_vars applied after the hook silently undid it.

    Both calls exist in the dispatch path and the hook must come second. Asserted at
    source level because the surrounding function needs a live orchestration state to
    call; the ordering is the invariant worth protecting from a careless edit.
    """
    src = (Path(__file__).resolve().parents[2] / "lib" / "set_orch" / "dispatcher.py").read_text()

    apply_at = src.rfind("_apply_env_vars_to_env_file(env_file")
    rerun_at = src.rfind("_rerun_project_worktree_init(project_path")

    assert apply_at != -1, "config env_vars are no longer applied in dispatch"
    assert rerun_at != -1, "the project worktree-init hook is not re-run after env_vars"
    assert rerun_at > apply_at, (
        "worktree-init hook runs BEFORE env_vars — config would overwrite the "
        "project's per-worktree isolation again"
    )
