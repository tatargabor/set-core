"""Tests for dep-drift defense in the web e2e gate.

Covers pre-gate drift detection, self-heal on MODULE_NOT_FOUND, and the
at-most-once self-heal invariant. See OpenSpec change:
e2e-auto-install-on-dep-drift.
"""

from __future__ import annotations

import json
import os
import time as _time
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from set_project_web import gates


# ─── Small test helpers ──────────────────────────────────────────────


def _write_pkg_json(wt, deps=None, dev_deps=None):
    data = {"name": "test", "version": "1.0.0"}
    if deps is not None:
        data["dependencies"] = deps
    if dev_deps is not None:
        data["devDependencies"] = dev_deps
    (wt / "package.json").write_text(json.dumps(data))


def _set_mtime(path, when):
    os.utime(str(path), (when, when))


@pytest.fixture
def wt(tmp_path):
    """Minimal worktree with package.json, node_modules/, and pnpm marker."""
    _write_pkg_json(tmp_path, dev_deps={"dotenv": "^16.0.0"})
    nm = tmp_path / "node_modules"
    nm.mkdir()
    marker = nm / ".modules.yaml"
    marker.write_text("lockfileVersion: 7\n")
    # Make marker newer than package.json (in sync)
    _set_mtime(tmp_path / "package.json", _time.time() - 10)
    _set_mtime(marker, _time.time())
    return tmp_path


# ─── _deps_drift_reason (task 1.2 / AC-1..AC-4) ──────────────────────


class TestDepsDriftReason:
    def test_in_sync_returns_none(self, wt):
        assert gates._deps_drift_reason(str(wt), "pnpm") is None

    def test_mtime_drift(self, wt):
        # package.json newer than marker
        now = _time.time()
        _set_mtime(wt / "package.json", now)
        _set_mtime(wt / "node_modules" / ".modules.yaml", now - 10)
        assert gates._deps_drift_reason(str(wt), "pnpm") == "mtime"

    def test_node_modules_missing(self, tmp_path):
        _write_pkg_json(tmp_path, dev_deps={"dotenv": "^16.0.0"})
        assert gates._deps_drift_reason(str(tmp_path), "pnpm") == "node_modules_missing"

    def test_marker_missing_but_node_modules_exists(self, tmp_path):
        _write_pkg_json(tmp_path, dev_deps={"dotenv": "^16.0.0"})
        (tmp_path / "node_modules").mkdir()
        assert gates._deps_drift_reason(str(tmp_path), "pnpm") == "marker_missing"

    def test_no_package_json_returns_none(self, tmp_path):
        assert gates._deps_drift_reason(str(tmp_path), "pnpm") is None


# ─── _extract_missing_module (task 1.4) ──────────────────────────────


class TestExtractMissingModule:
    def test_matches_full_signature(self):
        out = (
            "Error: Cannot find module 'dotenv/config'\n"
            "    code: 'MODULE_NOT_FOUND',\n"
        )
        assert gates._extract_missing_module(out) == "dotenv/config"

    def test_requires_module_not_found_literal(self):
        out = "Cannot find module 'foo'\n    at Module._resolveFilename"
        assert gates._extract_missing_module(out) is None

    def test_requires_regex_match(self):
        out = "Test failed with MODULE_NOT_FOUND somewhere in the stack"
        assert gates._extract_missing_module(out) is None

    def test_scoped_package(self):
        out = (
            "Error: Cannot find module '@radix-ui/react-slot'\n"
            "MODULE_NOT_FOUND\n"
        )
        assert gates._extract_missing_module(out) == "@radix-ui/react-slot"


# ─── _resolve_package_name (task 1.5 / AC-11) ────────────────────────


class TestResolvePackageName:
    def test_simple_name(self):
        assert gates._resolve_package_name("dotenv") == "dotenv"

    def test_simple_name_with_subpath(self):
        assert gates._resolve_package_name("dotenv/config") == "dotenv"

    def test_scoped_name_bare(self):
        assert gates._resolve_package_name("@radix-ui/react-slot") == "@radix-ui/react-slot"

    def test_scoped_name_with_subpath(self):
        assert (
            gates._resolve_package_name("@radix-ui/react-slot/dist/index.js")
            == "@radix-ui/react-slot"
        )

    def test_relative_path_unchanged(self):
        assert gates._resolve_package_name("./relative-file") == "./relative-file"

    def test_absolute_path_unchanged(self):
        assert gates._resolve_package_name("/abs/path") == "/abs/path"

    def test_empty_unchanged(self):
        assert gates._resolve_package_name("") == ""


# ─── _is_declared_in_package_json (task 1.6) ─────────────────────────


class TestIsDeclaredInPackageJson:
    def test_in_dependencies(self, tmp_path):
        _write_pkg_json(tmp_path, deps={"dotenv": "^16"})
        assert gates._is_declared_in_package_json(str(tmp_path), "dotenv") is True

    def test_in_dev_dependencies(self, tmp_path):
        _write_pkg_json(tmp_path, dev_deps={"dotenv": "^16"})
        assert gates._is_declared_in_package_json(str(tmp_path), "dotenv") is True

    def test_not_declared(self, tmp_path):
        _write_pkg_json(tmp_path, deps={"other": "^1"})
        assert gates._is_declared_in_package_json(str(tmp_path), "dotenv") is False

    def test_no_package_json(self, tmp_path):
        assert gates._is_declared_in_package_json(str(tmp_path), "dotenv") is False

    def test_malformed_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("{not valid json")
        assert gates._is_declared_in_package_json(str(tmp_path), "dotenv") is False

    def test_scoped_lookup(self, tmp_path):
        _write_pkg_json(tmp_path, deps={"@radix-ui/react-slot": "^1.2"})
        assert (
            gates._is_declared_in_package_json(str(tmp_path), "@radix-ui/react-slot")
            is True
        )


# ─── _ensure_deps_synced integration (task 2.x, AC-1..AC-6) ──────────


@dataclass
class _FakeProfile:
    pm: str = "pnpm"
    install_cmd: str = "pnpm install"

    def detect_package_manager(self, wt_path):
        return self.pm

    def detect_dep_install_command(self, wt_path):
        return self.install_cmd


class TestEnsureDepsSynced:
    def test_no_profile_no_op(self, wt):
        # No detect_package_manager on profile → no-op
        class NoPM:
            pass
        with patch("set_project_web.gates._run_dep_install") as run:
            gates._ensure_deps_synced(str(wt), NoPM(), "change-x")
        assert run.call_count == 0

    def test_no_drift_no_install(self, wt):
        with patch("set_project_web.gates._run_dep_install") as run:
            gates._ensure_deps_synced(str(wt), _FakeProfile(), "change-x")
        assert run.call_count == 0

    def test_drift_triggers_install(self, wt):
        now = _time.time()
        _set_mtime(wt / "package.json", now)
        _set_mtime(wt / "node_modules" / ".modules.yaml", now - 10)
        with patch("set_project_web.gates._run_dep_install", return_value=(0, 42, False)) as run:
            gates._ensure_deps_synced(str(wt), _FakeProfile(), "change-x")
        assert run.call_count == 1

    def test_install_timeout_does_not_raise(self, wt):
        now = _time.time()
        _set_mtime(wt / "package.json", now)
        _set_mtime(wt / "node_modules" / ".modules.yaml", now - 10)
        with patch(
            "set_project_web.gates._run_dep_install", return_value=(-1, _time.monotonic() and 0, True),
        ):
            # Must not raise
            gates._ensure_deps_synced(str(wt), _FakeProfile(), "change-x")


# ─── _self_heal_missing_module (task 3.x, AC-7..AC-13) ───────────────


@dataclass
class _FakeRunResult:
    exit_code: int = 0
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""


class TestSelfHealMissingModule:
    def test_no_match_returns_none(self, wt):
        # Output without MODULE_NOT_FOUND → no self-heal
        out = "Test failed: expected 1 but got 2"
        result = gates._self_heal_missing_module(
            str(wt), _FakeProfile(), out, "change-x",
            env={}, actual_e2e_cmd="pnpm test:e2e", e2e_timeout=60,
        )
        assert result is None

    def test_undeclared_module_returns_none(self, tmp_path):
        _write_pkg_json(tmp_path, deps={"other": "^1"})
        out = "Cannot find module './not-a-package'\nMODULE_NOT_FOUND"
        result = gates._self_heal_missing_module(
            str(tmp_path), _FakeProfile(), out, "change-x",
            env={}, actual_e2e_cmd="pnpm test:e2e", e2e_timeout=60,
        )
        assert result is None

    def test_declared_triggers_install_and_rerun(self, wt):
        out = "Error: Cannot find module 'dotenv/config'\nMODULE_NOT_FOUND"
        # Mock install success + rerun success
        rerun = _FakeRunResult(exit_code=0, stdout="33 passed (2s)", stderr="")
        with patch(
            "set_project_web.gates._run_dep_install",
            return_value=(0, 500, False),
        ) as install_mock, patch(
            "set_project_web.gates.run_command",
            create=True,
        ):
            # Patch run_command via the module where it's imported inside the function
            import set_orch.subprocess_utils as _su
            with patch.object(_su, "run_command", return_value=rerun) as rerun_mock:
                result = gates._self_heal_missing_module(
                    str(wt), _FakeProfile(), out, "change-x",
                    env={}, actual_e2e_cmd="pnpm test:e2e", e2e_timeout=60,
                )
        assert install_mock.call_count == 1
        assert result is not None
        healed, pkg, rerun_result = result
        assert pkg == "dotenv"
        assert healed is True
        assert rerun_mock.call_count == 1

    def test_declared_but_rerun_crashes(self, wt):
        out = "Error: Cannot find module 'dotenv/config'\nMODULE_NOT_FOUND"
        # install OK, but rerun ALSO crashes with same error
        rerun = _FakeRunResult(
            exit_code=1,
            stdout="Cannot find module 'dotenv/config'\nMODULE_NOT_FOUND",
        )
        import set_orch.subprocess_utils as _su
        with patch(
            "set_project_web.gates._run_dep_install",
            return_value=(0, 200, False),
        ), patch.object(_su, "run_command", return_value=rerun):
            result = gates._self_heal_missing_module(
                str(wt), _FakeProfile(), out, "change-x",
                env={}, actual_e2e_cmd="pnpm test:e2e", e2e_timeout=60,
            )
        assert result is not None
        healed, pkg, _rerun = result
        assert pkg == "dotenv"
        assert healed is False

    def test_scoped_declared_package(self, tmp_path):
        _write_pkg_json(
            tmp_path,
            deps={"@radix-ui/react-slot": "^1.2"},
        )
        (tmp_path / "node_modules").mkdir()
        out = "Error: Cannot find module '@radix-ui/react-slot'\nMODULE_NOT_FOUND"
        rerun = _FakeRunResult(exit_code=0, stdout="33 passed")
        import set_orch.subprocess_utils as _su
        with patch(
            "set_project_web.gates._run_dep_install",
            return_value=(0, 100, False),
        ), patch.object(_su, "run_command", return_value=rerun):
            result = gates._self_heal_missing_module(
                str(tmp_path), _FakeProfile(), out, "change-x",
                env={}, actual_e2e_cmd="pnpm test:e2e", e2e_timeout=60,
            )
        assert result is not None
        _healed, pkg, _rerun = result
        assert pkg == "@radix-ui/react-slot"


# ─── execute_e2e_gate integration (tasks 5.5 / 5.6 / 5.7 / 5.8 / 5.9) ─


def _make_e2e_worktree(tmp_path, deps=None, dev_deps=None):
    """Set up a minimal worktree that passes the execute_e2e_gate preconditions."""
    if dev_deps is None:
        dev_deps = {"dotenv": "^16.0.0"}
    _write_pkg_json(tmp_path, deps=deps, dev_deps=dev_deps)
    (tmp_path / "playwright.config.ts").write_text(
        'import "dotenv/config";\n'
        'export default {\n'
        '  testDir: "tests/e2e",\n'
        '  webServer: { command: "next dev", url: "http://localhost:3000" },\n'
        '};\n'
    )
    (tmp_path / "tests" / "e2e").mkdir(parents=True)
    (tmp_path / "tests" / "e2e" / "smoke.spec.ts").write_text("test('s', () => {});")
    (tmp_path / "node_modules").mkdir()
    return tmp_path


@dataclass
class _FakeChange:
    verify_retry_count: int = 0
    scope: str = "scope"
    extras: dict = field(default_factory=dict)


class TestExecuteE2eGatePreInstall:
    def test_drift_triggers_install_before_playwright(self, tmp_path, monkeypatch):
        wt = _make_e2e_worktree(tmp_path)
        marker = wt / "node_modules" / ".modules.yaml"
        marker.write_text("lockfileVersion: 7\n")
        now = _time.time()
        _set_mtime(wt / "package.json", now)
        _set_mtime(marker, now - 10)

        call_log: list[str] = []

        def fake_run_command(cmd, **kwargs):
            cmd_str = cmd[-1] if isinstance(cmd, list) else cmd
            call_log.append(cmd_str)
            if "install" in cmd_str:
                return _FakeRunResult(exit_code=0, stdout="deps installed")
            return _FakeRunResult(exit_code=0, stdout="33 passed (2s)")

        import set_orch.subprocess_utils as _su
        monkeypatch.setattr(_su, "run_command", fake_run_command)
        monkeypatch.setattr("set_project_web.gates._detect_main_worktree", lambda p: None)

        result = gates.execute_e2e_gate(
            "change-x", _FakeChange(), str(wt),
            "pnpm test:e2e", 60, 10,
            profile=_FakeProfile(),
        )
        assert result.status == "pass"
        assert any("install" in c for c in call_log), f"no install in {call_log}"
        install_idx = next(i for i, c in enumerate(call_log) if "install" in c)
        e2e_idx = next(
            (i for i, c in enumerate(call_log) if "test:e2e" in c or "playwright" in c),
            None,
        )
        if e2e_idx is not None:
            assert install_idx < e2e_idx

    def test_no_drift_no_install(self, tmp_path, monkeypatch):
        wt = _make_e2e_worktree(tmp_path)
        marker = wt / "node_modules" / ".modules.yaml"
        marker.write_text("lockfileVersion: 7\n")
        now = _time.time()
        _set_mtime(wt / "package.json", now - 10)
        _set_mtime(marker, now)

        call_log: list[str] = []

        def fake_run_command(cmd, **kwargs):
            cmd_str = cmd[-1] if isinstance(cmd, list) else cmd
            call_log.append(cmd_str)
            return _FakeRunResult(exit_code=0, stdout="33 passed (2s)")

        import set_orch.subprocess_utils as _su
        monkeypatch.setattr(_su, "run_command", fake_run_command)
        monkeypatch.setattr("set_project_web.gates._detect_main_worktree", lambda p: None)

        result = gates.execute_e2e_gate(
            "change-x", _FakeChange(), str(wt),
            "pnpm test:e2e", 60, 10,
            profile=_FakeProfile(),
        )
        assert result.status == "pass"
        assert all("install" not in c for c in call_log), f"unexpected install: {call_log}"


class TestExecuteE2eGateSelfHeal:
    def test_self_heal_on_module_not_found_for_declared_dep(self, tmp_path, monkeypatch):
        wt = _make_e2e_worktree(tmp_path)
        marker = wt / "node_modules" / ".modules.yaml"
        marker.write_text("lockfileVersion: 7\n")
        now = _time.time()
        _set_mtime(wt / "package.json", now - 10)
        _set_mtime(marker, now)

        call_log: list[str] = []

        def fake_run_command(cmd, **kwargs):
            cmd_str = cmd[-1] if isinstance(cmd, list) else cmd
            call_log.append(cmd_str)
            if "install" in cmd_str:
                return _FakeRunResult(exit_code=0, stdout="installed")
            e2e_calls = [c for c in call_log if "install" not in c]
            if len(e2e_calls) == 1:
                return _FakeRunResult(
                    exit_code=1,
                    stdout="Error: Cannot find module 'dotenv/config'\nMODULE_NOT_FOUND",
                )
            return _FakeRunResult(exit_code=0, stdout="33 passed (2s)")

        import set_orch.subprocess_utils as _su
        monkeypatch.setattr(_su, "run_command", fake_run_command)
        monkeypatch.setattr("set_project_web.gates._detect_main_worktree", lambda p: None)

        result = gates.execute_e2e_gate(
            "change-x", _FakeChange(), str(wt),
            "pnpm test:e2e", 60, 10,
            profile=_FakeProfile(),
        )
        assert result.status == "pass"
        assert result.output.startswith("[self-heal: installed dotenv]\n\n")
        install_calls = [c for c in call_log if "install" in c]
        e2e_calls = [c for c in call_log if "install" not in c]
        assert len(install_calls) == 1
        assert len(e2e_calls) == 2

    def test_no_self_heal_for_undeclared_module(self, tmp_path, monkeypatch):
        wt = _make_e2e_worktree(tmp_path, dev_deps={"other": "^1"})
        marker = wt / "node_modules" / ".modules.yaml"
        marker.write_text("lockfileVersion: 7\n")
        now = _time.time()
        _set_mtime(wt / "package.json", now - 10)
        _set_mtime(marker, now)

        call_log: list[str] = []

        def fake_run_command(cmd, **kwargs):
            cmd_str = cmd[-1] if isinstance(cmd, list) else cmd
            call_log.append(cmd_str)
            if "install" in cmd_str:
                return _FakeRunResult(exit_code=0, stdout="installed")
            return _FakeRunResult(
                exit_code=1,
                stdout="Error: Cannot find module './nonexistent'\nMODULE_NOT_FOUND",
            )

        import set_orch.subprocess_utils as _su
        monkeypatch.setattr(_su, "run_command", fake_run_command)
        monkeypatch.setattr("set_project_web.gates._detect_main_worktree", lambda p: None)

        result = gates.execute_e2e_gate(
            "change-x", _FakeChange(), str(wt),
            "pnpm test:e2e", 60, 10,
            profile=_FakeProfile(),
        )
        assert result.status == "fail"
        assert "[self-heal" not in (result.output or "")
        install_calls = [c for c in call_log if "install" in c]
        assert len(install_calls) == 0

    def test_self_heal_rerun_still_crashes_unparseable(self, tmp_path, monkeypatch):
        wt = _make_e2e_worktree(tmp_path)
        marker = wt / "node_modules" / ".modules.yaml"
        marker.write_text("lockfileVersion: 7\n")
        now = _time.time()
        _set_mtime(wt / "package.json", now - 10)
        _set_mtime(marker, now)

        call_log: list[str] = []

        def fake_run_command(cmd, **kwargs):
            cmd_str = cmd[-1] if isinstance(cmd, list) else cmd
            call_log.append(cmd_str)
            if "install" in cmd_str:
                return _FakeRunResult(exit_code=0, stdout="installed")
            return _FakeRunResult(
                exit_code=1,
                stdout="Error: Cannot find module 'dotenv/config'\nMODULE_NOT_FOUND",
            )

        import set_orch.subprocess_utils as _su
        monkeypatch.setattr(_su, "run_command", fake_run_command)
        monkeypatch.setattr("set_project_web.gates._detect_main_worktree", lambda p: None)

        result = gates.execute_e2e_gate(
            "change-x", _FakeChange(), str(wt),
            "pnpm test:e2e", 60, 10,
            profile=_FakeProfile(),
        )
        assert result.status == "fail"
        assert result.retry_context is not None
        assert "self-heal attempted for 'dotenv'" in result.retry_context
        assert "rerun also crashed" in result.retry_context

    def test_self_heal_at_most_once(self, tmp_path, monkeypatch):
        wt = _make_e2e_worktree(tmp_path)
        marker = wt / "node_modules" / ".modules.yaml"
        marker.write_text("lockfileVersion: 7\n")
        now = _time.time()
        _set_mtime(wt / "package.json", now)
        _set_mtime(marker, now - 10)

        call_log: list[str] = []

        def fake_run_command(cmd, **kwargs):
            cmd_str = cmd[-1] if isinstance(cmd, list) else cmd
            call_log.append(cmd_str)
            if "install" in cmd_str:
                return _FakeRunResult(exit_code=0, stdout="installed")
            return _FakeRunResult(
                exit_code=1,
                stdout="Error: Cannot find module 'dotenv/config'\nMODULE_NOT_FOUND",
            )

        import set_orch.subprocess_utils as _su
        monkeypatch.setattr(_su, "run_command", fake_run_command)
        monkeypatch.setattr("set_project_web.gates._detect_main_worktree", lambda p: None)

        result = gates.execute_e2e_gate(
            "change-x", _FakeChange(), str(wt),
            "pnpm test:e2e", 60, 10,
            profile=_FakeProfile(),
        )
        assert result.status == "fail"
        install_calls = [c for c in call_log if "install" in c]
        assert len(install_calls) == 2, f"expected 2, got {len(install_calls)}: {call_log}"
