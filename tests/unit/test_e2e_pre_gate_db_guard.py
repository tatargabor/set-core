"""`e2e_pre_gate` must refuse DB mutation against a non-disposable target (0'b).

The guard used to read `DATABASE_URL` from the worktree `.env` FILE while the
`prisma db push --accept-data-loss` and `db seed` it protects run with the
`env` PARAMETER merged over `os.environ`. So it inspected the lowest-priority
source while the command used the highest, and it never fired at all when the
file was missing or lacked the key — the case where the target is least known.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "modules", "web"),
)

from set_project_web.project_type import WebProjectType  # noqa: E402


@pytest.fixture
def wt(tmp_path):
    """Worktree with a prisma schema and a seed file (both commands reachable)."""
    (tmp_path / "prisma").mkdir()
    (tmp_path / "prisma" / "schema.prisma").write_text(
        'datasource db {\n  provider = "postgresql"\n}\n'
    )
    (tmp_path / "prisma" / "seed.ts").write_text("// seed\n")
    return tmp_path


def _write_env(wt, value):
    (wt / ".env").write_text(f'DATABASE_URL="{value}"\n')


def run_pre_gate(wt, env, ambient=None):
    """Run e2e_pre_gate with subprocess captured. Returns (result, commands)."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    profile = WebProjectType()
    with patch("subprocess.run", side_effect=fake_run):
        with patch.dict(os.environ, ambient or {}, clear=False):
            if ambient is None:
                os.environ.pop("DATABASE_URL", None)
            result = profile.e2e_pre_gate(str(wt), env)
    return result, calls


def _mutating(calls):
    """Commands that write to the database."""
    return [c for c in calls if "db" in c and ("push" in c or "seed" in c)]


class TestRefusesNonDisposableTargets:
    def test_postgres_in_env_parameter(self, wt):
        """The parameter is what the subprocess actually gets."""
        result, calls = run_pre_gate(
            wt, {"DATABASE_URL": "postgresql://user:pw@localhost:5432/app"}
        )

        assert result is True  # non-fatal skip, not a gate failure
        assert _mutating(calls) == []

    def test_env_parameter_overrides_a_disposable_file(self, wt):
        """The exact hole: file says file:, parameter says postgres."""
        _write_env(wt, "file:./dev.db")

        result, calls = run_pre_gate(
            wt, {"DATABASE_URL": "postgresql://user:pw@prod-mirror/app"}
        )

        assert result is True
        assert _mutating(calls) == []

    def test_missing_env_file_entirely(self, wt):
        """No file → old guard never fired and the push ran regardless."""
        result, calls = run_pre_gate(wt, {})

        assert result is True
        assert _mutating(calls) == []

    def test_env_file_without_database_url(self, wt):
        (wt / ".env").write_text("PORT=3000\nNEXTAUTH_URL=http://localhost\n")

        result, calls = run_pre_gate(wt, {})

        assert result is True
        assert _mutating(calls) == []

    def test_empty_database_url(self, wt):
        result, calls = run_pre_gate(wt, {"DATABASE_URL": ""})

        assert result is True
        assert _mutating(calls) == []

    def test_ambient_environment_target(self, wt):
        """Inherited via `{**os.environ, **env}` even with no file and no param."""
        result, calls = run_pre_gate(
            wt, {}, ambient={"DATABASE_URL": "mysql://root@localhost/app"}
        )

        assert result is True
        assert _mutating(calls) == []

    def test_seed_is_refused_too(self, wt):
        """Seeding writes rows; the early return must cover it."""
        _write_env(wt, "postgresql://localhost/app")

        _result, calls = run_pre_gate(wt, {})

        assert not any("seed" in c for c in calls)


class TestAllowsDisposableTargets:
    def test_sqlite_from_env_parameter(self, wt):
        result, calls = run_pre_gate(wt, {"DATABASE_URL": "file:./test.db"})

        assert result is True
        assert any("push" in c for c in calls)

    def test_sqlite_from_env_file(self, wt):
        _write_env(wt, "file:./dev.db")

        result, calls = run_pre_gate(wt, {})

        assert result is True
        assert any("push" in c for c in calls)

    def test_sqlite_runs_seed(self, wt):
        _write_env(wt, "file:./dev.db")

        _result, calls = run_pre_gate(wt, {})

        assert any("seed" in c for c in calls)

    def test_parameter_file_beats_ambient_postgres(self, wt):
        """The parameter wins in the subprocess, so it must win in the guard."""
        result, calls = run_pre_gate(
            wt,
            {"DATABASE_URL": "file:./test.db"},
            ambient={"DATABASE_URL": "postgresql://localhost/app"},
        )

        assert result is True
        assert any("push" in c for c in calls)


class TestUnrelatedBehaviourPreserved:
    def test_no_prisma_schema_returns_early(self, tmp_path):
        result, calls = run_pre_gate(tmp_path, {"DATABASE_URL": "file:./x.db"})

        assert result is True
        assert calls == []

    def test_no_seed_file_still_pushes(self, wt):
        (wt / "prisma" / "seed.ts").unlink()
        _write_env(wt, "file:./dev.db")

        _result, calls = run_pre_gate(wt, {})

        assert any("push" in c for c in calls)
        assert not any("seed" in c for c in calls)


class TestResolutionOrder:
    """Mirrors `env={**os.environ, **env}` plus Prisma's own `.env` loading."""

    def test_parameter_first(self, wt):
        _write_env(wt, "file:./file.db")
        profile = WebProjectType()

        with patch.dict(os.environ, {"DATABASE_URL": "mysql://ambient/db"}):
            resolved = profile._resolve_effective_database_url(
                str(wt), {"DATABASE_URL": "postgres://param/db"}
            )

        assert resolved == "postgres://param/db"

    def test_ambient_second(self, wt):
        _write_env(wt, "file:./file.db")
        profile = WebProjectType()

        with patch.dict(os.environ, {"DATABASE_URL": "mysql://ambient/db"}):
            resolved = profile._resolve_effective_database_url(str(wt), {})

        assert resolved == "mysql://ambient/db"

    def test_file_last(self, wt):
        _write_env(wt, "file:./file.db")
        profile = WebProjectType()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            resolved = profile._resolve_effective_database_url(str(wt), {})

        assert resolved == "file:./file.db"

    def test_empty_string_does_not_shadow(self, wt):
        """An empty parameter must not hide a real ambient value."""
        _write_env(wt, "file:./file.db")
        profile = WebProjectType()

        with patch.dict(os.environ, {"DATABASE_URL": "mysql://ambient/db"}):
            resolved = profile._resolve_effective_database_url(
                str(wt), {"DATABASE_URL": ""}
            )

        assert resolved == "mysql://ambient/db"
