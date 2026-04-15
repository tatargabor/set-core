"""Web-specific gate executors — e2e (Playwright) and lint (forbidden patterns).

Moved from lib/set_orch/verifier.py as part of profile-driven-gate-registry.
These executors are registered by WebProjectType.register_gates().
"""

from __future__ import annotations

import fcntl
import fnmatch
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from set_orch.state import Change

logger = logging.getLogger(__name__)

# E2E capture ceiling — large enough to hold the full Playwright output for
# extreme failure counts (200+ failures with long stack traces or multi-KB
# JSON diffs). The downstream state storage in gate_runner applies a tighter
# pattern-preserving bound (32KB) via smart_truncate_structured. This value
# only affects the transient capture used for failure-ID extraction and
# baseline comparison — raising it has no persistent cost.
_E2E_CAPTURE_MAX_BYTES = 4 * 1024 * 1024  # 4 MiB

# Dedicated port for the baseline regeneration run. Deliberately far from
# the default worktree port base (3100) so a live worktree dev server never
# collides with the baseline. See OpenSpec change: harden-e2e-baseline-cache.
_E2E_BASELINE_PORT = 3199

# Runtime error indicators in E2E output — if any appear, the page has client-side errors
# even if HTTP returned 200.
E2E_RUNTIME_ERROR_INDICATORS = [
    "Functions are not valid as a child",
    "Hydration failed because",
    "There was an error while hydrating",
    "Minified React error",
    "Error: Text content does not match",
    "Unhandled Runtime Error",
    "data-nextjs-error",
    "Internal error: Error: ",
]


# ─── E2E Helpers ─────────────────────────────────────────────────────


def _check_e2e_runtime_errors(output: str) -> list[str]:
    """Scan E2E output for client-side runtime error indicators."""
    found = []
    output_lower = output.lower()
    for indicator in E2E_RUNTIME_ERROR_INDICATORS:
        if indicator.lower() in output_lower:
            found.append(indicator)
    return found


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _extract_e2e_failure_ids(output: str) -> set[str]:
    """Extract unique failure identifiers from Playwright output.

    Strips ANSI escape sequences first. Playwright emits cursor-control
    codes (`\\x1b[1A\\x1b[2K`) before each progress line when stdout is
    a terminal-like stream; the `^\\s*` anchor in the failure regex does
    not match escape bytes, so without stripping we miss every failure
    and hand control to the "unparseable crash" guard, which then fires
    a misleading retry_context ("likely crash, OOM, or formatter issue")
    on a perfectly parseable assertion failure. Caught on
    nano-run-20260412-1941 where a `toHaveCount({min: 2})` assertion
    error was misdiagnosed as a crash.
    """
    clean = _ANSI_ESCAPE_RE.sub("", output)
    ids: set[str] = set()
    for m in re.finditer(r"^\s*\d+\)\s+\[.*?\]\s+[›»]\s+([^\s:]+\.spec\.\w+:\d+)", clean, re.MULTILINE):
        ids.add(m.group(1))
    return ids


def _parse_playwright_config(wt_path: str) -> dict:
    """Parse Playwright config for testDir and webServer presence."""
    config_path = None
    for name in ("playwright.config.ts", "playwright.config.js"):
        candidate = os.path.join(wt_path, name)
        if os.path.isfile(candidate):
            config_path = candidate
            break

    if not config_path:
        return {"config_path": None, "test_dir": None, "has_web_server": False}

    try:
        with open(config_path) as f:
            content = f.read()
    except OSError:
        return {"config_path": config_path, "test_dir": None, "has_web_server": False}

    test_dir = None
    m = re.search(r'testDir:\s*["\']([^"\']+)["\']', content)
    if m:
        raw = m.group(1)
        test_dir = raw.lstrip("./") if raw.startswith("./") else raw

    has_web_server = "webServer" in content

    return {
        "config_path": config_path,
        "test_dir": test_dir,
        "has_web_server": has_web_server,
    }


def _count_e2e_tests(wt_path: str, pw_config: dict | None = None) -> tuple[int, str]:
    """Count E2E test files in worktree."""
    if pw_config is None:
        pw_config = _parse_playwright_config(wt_path)

    if not pw_config["config_path"]:
        return 0, ""

    test_dir = pw_config.get("test_dir")
    if test_dir:
        search_dirs = [test_dir]
    else:
        search_dirs = ["tests/e2e", "e2e", "test/e2e", "tests"]

    count = 0
    searched = []
    for d in search_dirs:
        abs_dir = os.path.join(wt_path, d)
        if not os.path.isdir(abs_dir):
            continue
        searched.append(d)
        for _root, _dirs, files in os.walk(abs_dir):
            for f in files:
                if f.endswith(".spec.ts") or f.endswith(".spec.js"):
                    count += 1

    searched_desc = ", ".join(searched) if searched else ", ".join(search_dirs)
    return count, searched_desc


def _detect_main_worktree(wt_path: str) -> str | None:
    """Detect the main checkout path from a worktree's perspective.

    Returns the main worktree path or None if detection is unreliable.
    Fail-closed: callers should skip baseline comparison on None rather
    than fall back to a heuristic parent-dir guess. See OpenSpec change:
    harden-e2e-baseline-cache.
    """
    from set_orch.subprocess_utils import run_git

    # Connectivity probe — if git cannot resolve the worktree, abort.
    # We don't use the stdout of rev-parse; worktree list below provides
    # the full topology we need.
    git_probe = run_git("rev-parse", "--show-toplevel", cwd=wt_path)
    if git_probe.exit_code != 0:
        logger.info("Main worktree detection failed: rev-parse exit=%d", git_probe.exit_code)
        return None

    wt_list = run_git("worktree", "list", "--porcelain", cwd=wt_path)
    if wt_list.exit_code != 0:
        logger.info("Main worktree detection failed: worktree list exit=%d", wt_list.exit_code)
        return None

    wt_basename = os.path.basename(wt_path.rstrip("/"))
    main_path: str | None = None
    for line in wt_list.stdout.split("\n"):
        if not line.startswith("worktree "):
            continue
        candidate = line.split(" ", 1)[1].strip()
        if not candidate:
            continue
        if os.path.basename(candidate.rstrip("/")) == wt_basename:
            continue
        main_path = candidate
        break

    if not main_path:
        logger.info("Main worktree detection failed: no main entry in worktree list")
        return None

    # Validate: main_path must exist and contain a .git entry (file or dir).
    if not os.path.isdir(main_path):
        logger.info("Main worktree detection failed: %s is not a directory", main_path)
        return None
    git_entry = os.path.join(main_path, ".git")
    if not os.path.exists(git_entry):
        logger.info("Main worktree detection failed: %s has no .git entry", main_path)
        return None

    return main_path


def _is_project_root_clean(project_root: str) -> bool:
    """Return True if project_root has no uncommitted changes.

    A dirty root means the baseline run may capture ephemeral state that
    does not reflect main's real behavior. See OpenSpec change:
    harden-e2e-baseline-cache.
    """
    from set_orch.subprocess_utils import run_git

    status = run_git("status", "--porcelain", cwd=project_root)
    if status.exit_code != 0:
        # Treat unknown as dirty — safer not to persist
        return False
    return status.stdout.strip() == ""


def _baseline_lock_path(baseline_path: str) -> str:
    """Return the sidecar lock file path next to the baseline cache."""
    return baseline_path + ".lock"


def _get_or_create_e2e_baseline(
    e2e_command: str, e2e_timeout: int, project_root: str,
    profile: "object | None" = None,
) -> dict | None:
    """Run Playwright on main and cache baseline failures."""
    from set_orch.subprocess_utils import run_command, run_git
    from set_orch.verifier import parse_test_output

    try:
        from set_orch.paths import SetRuntime
        baseline_path = os.path.join(SetRuntime().orchestration_dir, "e2e-baseline.json")
    except Exception:
        baseline_path = os.path.join("set", "orchestration", "e2e-baseline.json")

    def _load_cached_if_fresh(sha: str) -> dict | None:
        """Return the on-disk cache if its main_sha matches; else None."""
        if not os.path.isfile(baseline_path):
            return None
        try:
            with open(baseline_path) as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None
        if data.get("main_sha") != sha:
            return None
        data["failures"] = set(data.get("failures", []))
        return data

    main_sha = run_git("rev-parse", "HEAD", cwd=project_root).stdout.strip()
    fresh = _load_cached_if_fresh(main_sha)
    if fresh is not None:
        return fresh
    if os.path.isfile(baseline_path):
        logger.info("E2E baseline stale (main moved to %s) — regenerating", main_sha[:8])

    # Dirty-tree check BEFORE acquiring the lock so concurrent callers
    # don't all run the check — cheap and idempotent. Best-effort only:
    # between this check and the actual baseline run, the tree can change
    # (another process editing the main checkout mid-orchestration). The
    # check's purpose is to avoid persisting a likely-stale baseline, not
    # to guarantee cleanliness — the main_sha invalidation covers the
    # cache-correctness side of the same concern.
    clean_root = _is_project_root_clean(project_root)
    if not clean_root:
        logger.warning(
            "E2E baseline: dirty project root at %s — running baseline but "
            "not caching (cacheable=False)",
            project_root,
        )

    # Acquire an exclusive lock on the sidecar .lock file so concurrent
    # callers do not race to regenerate. The lock is held for the full
    # duration of the baseline run (can be minutes).
    lock_path = _baseline_lock_path(baseline_path)
    os.makedirs(os.path.dirname(baseline_path), exist_ok=True)

    # Open lock file for writing and acquire exclusive lock
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        # Re-check after lock acquisition — a peer may have regenerated
        # while we were waiting. This avoids spawning a duplicate e2e run.
        fresh = _load_cached_if_fresh(main_sha)
        if fresh is not None:
            logger.info("E2E baseline: peer regenerated while we waited — reusing")
            return fresh

        logger.info("Creating E2E baseline on main (%s)...", main_sha[:8])

        # Build an isolated env with a dedicated baseline port so the
        # baseline dev server cannot collide with a live worktree server.
        # Order matters: profile-provided keys first, then our explicit
        # PW_PORT last so the constant always wins — no profile can
        # accidentally override the dedicated baseline port.
        baseline_env: dict[str, str] = {}
        if profile is not None and hasattr(profile, "e2e_gate_env"):
            try:
                try:
                    baseline_env.update(profile.e2e_gate_env(
                        _E2E_BASELINE_PORT,
                        timeout_seconds=e2e_timeout,
                        fresh_server=True,
                    ))
                except TypeError:
                    baseline_env.update(profile.e2e_gate_env(_E2E_BASELINE_PORT))
            except Exception:
                logger.debug("profile.e2e_gate_env failed for baseline port", exc_info=True)
        baseline_env["PW_PORT"] = str(_E2E_BASELINE_PORT)

        # Capture up to 4MB so _extract_e2e_failure_ids sees every failure.
        result = run_command(
            ["bash", "-c", e2e_command],
            timeout=e2e_timeout, cwd=project_root,
            env=baseline_env,
            max_output_size=_E2E_CAPTURE_MAX_BYTES,
        )
        output = result.stdout + result.stderr
        stats = parse_test_output(output)
        failures = _extract_e2e_failure_ids(output)

        baseline = {
            "main_sha": main_sha,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "failures": list(failures),
            "total": stats.get("total", 0),
            "passed": stats.get("passed", 0),
            "failed": stats.get("failed", 0),
            "cacheable": clean_root,
        }

        if clean_root:
            # Atomic temp-file-plus-rename so a crashed writer cannot leave
            # a partial JSON on disk.
            fd, tmp_path = tempfile.mkstemp(
                prefix=".e2e-baseline.",
                suffix=".tmp",
                dir=os.path.dirname(baseline_path),
            )
            try:
                with os.fdopen(fd, "w") as tmp_fh:
                    json.dump(baseline, tmp_fh, indent=2)
                os.rename(tmp_path, baseline_path)
                logger.info(
                    "E2E baseline cached: %d passed, %d failed on main",
                    baseline["passed"], baseline["failed"],
                )
            except OSError as exc:
                logger.warning("Failed to cache E2E baseline: %s", exc)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        else:
            logger.info(
                "E2E baseline not persisted (dirty project root, in-memory only)"
            )

        # Return with set-typed failures for the caller's convenience
        baseline["failures"] = failures
        return baseline
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(lock_fd)


def _kill_stale_listeners_on_port(port: int) -> None:
    """Kill any process bound to `port` — best-effort, non-fatal on failure.

    Called BEFORE spawning Playwright so a zombie `next start` from a prior
    crashed gate doesn't hold the port. Playwright's webServer aborts
    immediately with "port already used" when the port is occupied — its
    start happens BEFORE globalSetup, so we can't rely on a TypeScript-level
    kill hook. This must run from the gate-runner itself.
    """
    if port <= 0:
        return
    try:
        r = subprocess.run(
            ["lsof", "-t", "-i", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return
    if r.returncode not in (0, 1):  # 0=found, 1=none
        return
    pids = [p for p in (r.stdout or "").split() if p.isdigit()]
    if not pids:
        return
    logger.warning(
        "Killing %d stale process(es) bound to port %d: %s",
        len(pids), port, ", ".join(pids),
    )
    for pid_str in pids:
        try:
            os.kill(int(pid_str), 9)  # SIGKILL — zombie server, forget graceful
        except (OSError, ValueError) as exc:
            logger.debug("kill(%s) failed: %s", pid_str, exc)
    # Brief settle so the kernel actually releases the socket before playwright
    # tries to bind. Without this, SO_REUSEADDR races sometimes fail.
    time.sleep(0.5)


def _auto_detect_e2e_command(wt_path: str, profile=None) -> str:
    """Auto-detect e2e command by delegating to the project-type profile."""
    if profile is not None and hasattr(profile, "detect_e2e_command"):
        try:
            cmd = profile.detect_e2e_command(wt_path)
            if cmd:
                logger.info("E2E command detected via profile: %s", cmd)
                return cmd
        except Exception:
            pass
    return ""


# ─── E2E Gate Executor ───────────────────────────────────────────────


def execute_e2e_gate(
    change_name: str, change: "Change", wt_path: str,
    e2e_command: str, e2e_timeout: int, e2e_health_timeout: int,
    profile=None,
) -> "GateResult":
    """E2E gate: run Playwright tests with baseline comparison.

    Only NEW failures (not present on main) count as gate failures.
    Requires Playwright webServer config to manage the dev server.
    """
    from set_orch.gate_runner import GateResult
    from set_orch.subprocess_utils import run_command, run_git
    from set_orch.verifier import parse_test_output

    # Auto-detect e2e_command if not explicitly configured
    auto_detected = False
    if not e2e_command and wt_path:
        e2e_command = _auto_detect_e2e_command(wt_path, profile)
        auto_detected = bool(e2e_command)

    if not e2e_command or not wt_path:
        return GateResult("e2e", "skipped", output="e2e_command not configured")

    pw_config = _parse_playwright_config(wt_path)
    if not pw_config["config_path"]:
        return GateResult("e2e", "skipped",
                          output="no playwright.config.ts/js found in worktree")

    e2e_test_count, searched_desc = _count_e2e_tests(wt_path, pw_config)
    if e2e_test_count == 0:
        if auto_detected:
            scope = change.scope or ""
            return GateResult(
                "e2e", "fail",
                output=f"no e2e test files found (searched: {searched_desc})",
                retry_context=(
                    "E2E tests required for feature changes when Playwright is configured.\n\n"
                    f"Playwright config found but no test files in: {searched_desc}\n\n"
                    "Write E2E tests for the implemented functionality, then commit them.\n\n"
                    f"Original scope: {scope}"
                ),
            )
        return GateResult("e2e", "skipped",
                          output=f"no e2e test files found (searched: {searched_desc})")

    if not pw_config["has_web_server"]:
        return GateResult("e2e", "skipped",
                          output="playwright.config has no webServer — "
                                 "Playwright must manage the dev server via webServer config")

    # Build env with port isolation + gate-budget alignment from profile.
    # Passing `timeout_seconds` makes Playwright's `globalTimeout` match the
    # outer gate budget so a 600s gate doesn't get killed while playwright is
    # still racing its own 3600s cap. `fresh_server=True` signals the webServer
    # to skip `reuseExistingServer` — zombie-proof, stale-cache-proof.
    #
    # Port resolution order:
    #   1. change.extras.assigned_e2e_port — persisted at dispatch; stable
    #      across profile reloads, visible in state for observability.
    #   2. profile.worktree_port(change_name) — deterministic fallback when
    #      the dispatcher hasn't persisted yet (legacy changes, forward-compat).
    e2e_env: dict[str, str] = {}
    try:
        _assigned = int(change.extras.get("assigned_e2e_port", 0))
    except (TypeError, ValueError):
        _assigned = 0

    port = 0
    if _assigned > 0:
        port = _assigned
    elif profile and hasattr(profile, "worktree_port"):
        port = int(profile.worktree_port(change_name) or 0)

    # Pre-emptively kill any process bound to our assigned port BEFORE
    # Playwright boots its webServer. globalSetup runs AFTER the webServer
    # start, so the "kill stale port" logic in tests/e2e/global-setup.ts
    # can't protect against a pre-existing zombie — Playwright exits with
    # "port already used" before globalSetup gets a chance. Doing it here,
    # at the gate-runner level, catches the failure mode observed on
    # craftbrew-run-20260415-0146 auth-and-accounts (4 retries all failed
    # with port-in-use, no parseable failure list).
    if port > 0:
        _kill_stale_listeners_on_port(port)

    if port > 0 and profile and hasattr(profile, "e2e_gate_env"):
        try:
            e2e_env.update(profile.e2e_gate_env(
                port, timeout_seconds=e2e_timeout, fresh_server=True,
            ))
        except TypeError:
            # Back-compat for older profile signatures.
            e2e_env.update(profile.e2e_gate_env(port))
    # Fallback: read PORT from worktree .env if profile didn't set it
    if "PW_PORT" not in e2e_env:
        env_file = os.path.join(wt_path, ".env")
        if os.path.isfile(env_file):
            try:
                for line in open(env_file):
                    if line.startswith("PW_PORT="):
                        e2e_env["PW_PORT"] = line.strip().split("=", 1)[1]
                    elif line.startswith("PORT=") and "PORT" not in e2e_env:
                        e2e_env["PORT"] = line.strip().split("=", 1)[1]
            except OSError:
                pass

    # Pre-gate hook (DB setup, migrations, seed)
    if profile and hasattr(profile, "e2e_pre_gate"):
        if not profile.e2e_pre_gate(wt_path, e2e_env):
            return GateResult("e2e", "skipped", output="e2e_pre_gate returned False")

    # Run E2E tests.
    # Capture up to 4MB of output — _extract_e2e_failure_ids needs to see
    # every failure entry, including long assertion diffs and stack traces.
    # The subprocess_utils default of 1MB is enough for ~200 typical
    # failures but can truncate suites that fail on huge JSON diffs.
    # 4MB covers extreme edge cases without meaningful memory cost
    # (one short-lived string per gate run). Downstream state storage
    # still bounds the persisted value at 32KB via gate_runner's
    # smart_truncate_structured with a Playwright-aware keep pattern.
    try:
        e2e_cmd_result = run_command(
            ["bash", "-c", e2e_command],
            timeout=e2e_timeout, cwd=wt_path, env=e2e_env,
            max_output_size=_E2E_CAPTURE_MAX_BYTES,
        )
    finally:
        # Post-gate hook (cleanup) — always runs
        if profile and hasattr(profile, "e2e_post_gate"):
            try:
                profile.e2e_post_gate(wt_path)
            except Exception:
                pass  # non-fatal cleanup
    e2e_output = e2e_cmd_result.stdout + e2e_cmd_result.stderr

    # Collect screenshots
    try:
        from set_orch.paths import SetRuntime
        e2e_sc_dir = os.path.join(SetRuntime().screenshots_dir, "e2e", change_name)
    except Exception:
        e2e_sc_dir = f"set/orchestration/e2e-screenshots/{change_name}"
    os.makedirs(e2e_sc_dir, exist_ok=True)
    wt_test_results = os.path.join(wt_path, "test-results")
    if os.path.isdir(wt_test_results):
        for item in os.listdir(wt_test_results):
            src = os.path.join(wt_test_results, item)
            dst = os.path.join(e2e_sc_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    raw_status = "pass" if e2e_cmd_result.exit_code == 0 else "fail"

    # Check for runtime errors even on pass
    runtime_errors = _check_e2e_runtime_errors(e2e_output)
    if runtime_errors:
        logger.warning(
            "E2E runtime errors detected for %s: %s",
            change_name, ", ".join(runtime_errors),
        )

    if raw_status == "pass":
        # Pass the full captured output to gate_runner — it handles
        # pattern-preserving truncation to 32KB at the storage boundary.
        if runtime_errors:
            output_text = (
                f"WARNING: {len(runtime_errors)} runtime error(s) detected in E2E output: "
                f"{', '.join(runtime_errors)}\n\n" + e2e_output
            )
        else:
            output_text = e2e_output
        return GateResult(
            "e2e", "pass", output=output_text,
            stats=parse_test_output(e2e_output) if e2e_output else None,
        )

    # Timeout guard: an incomplete run cannot be compared against baseline —
    # the numbered failure list only arrives after the suite finishes, so a
    # timed-out run always produces wt_failures=set() and would otherwise
    # masquerade as PASS via the baseline branch below.
    if e2e_cmd_result.timed_out:
        logger.warning(
            "E2E gate timed out for %s after %ds — marking fail (no baseline comparison)",
            change_name, e2e_timeout,
        )
        return GateResult(
            "e2e", "fail",
            output=(
                f"E2E timed out after {e2e_timeout}s — Playwright did not finish "
                f"(incomplete run, cannot assess failures)\n\n"
                + e2e_output
            ),
            retry_context=(
                f"E2E gate timed out after {e2e_timeout}s. The test suite did not "
                f"finish executing — this is an infrastructure signal, not an "
                f"assertion failure. Check: webServer startup time, prisma db push "
                f"duration, test count, slow fixtures, network-bound tests. "
                f"Consider increasing e2e_timeout or marking slow tests with a "
                f"dedicated tag."
            ),
            stats=parse_test_output(e2e_output) if e2e_output else None,
        )

    # E2E failed — check baseline to filter pre-existing failures
    wt_failures = _extract_e2e_failure_ids(e2e_output)

    # Unparseable-fail guard: non-zero exit with no extractable failure IDs
    # means Playwright crashed or the formatter output was garbled — the
    # baseline comparison cannot help here, and would mask the failure as PASS.
    if not wt_failures:
        logger.warning(
            "E2E gate failed for %s with exit_code=%d but no parseable failure list "
            "— marking fail (no baseline comparison)",
            change_name, e2e_cmd_result.exit_code,
        )
        return GateResult(
            "e2e", "fail",
            output=(
                f"E2E exited with code {e2e_cmd_result.exit_code} but no parseable "
                f"failure list — likely crash, OOM, or formatter issue\n\n"
                + e2e_output
            ),
            retry_context=(
                f"E2E gate failed with exit_code={e2e_cmd_result.exit_code} but "
                f"Playwright did not emit a failure list. This usually means the "
                f"suite crashed before completing — check the worktree for stack "
                f"traces, OOM kills, webServer startup errors, or a Playwright "
                f"reporter that differs from the default."
            ),
            stats=parse_test_output(e2e_output) if e2e_output else None,
        )

    # Detect the main worktree via a strict helper that returns None when
    # git topology is unreliable. When None, skip baseline comparison and
    # treat every wt failure as new — fail-closed.
    project_root = _detect_main_worktree(wt_path)

    baseline = None
    if project_root is None:
        logger.info(
            "main worktree detection unreliable for %s — skipping baseline comparison (fail-closed)",
            change_name,
        )
    else:
        try:
            baseline = _get_or_create_e2e_baseline(
                e2e_command, e2e_timeout, project_root, profile=profile,
            )
        except Exception as e:
            logger.warning("E2E baseline creation failed (using all-failures mode): %s", e)

    if baseline:
        baseline_failures = baseline.get("failures", set())
        if isinstance(baseline_failures, list):
            baseline_failures = set(baseline_failures)
        new_failures = wt_failures - baseline_failures
        pre_existing = wt_failures & baseline_failures
        logger.info(
            "E2E baseline comparison: %d new failures, %d pre-existing on main",
            len(new_failures), len(pre_existing),
        )
        if not new_failures:
            return GateResult(
                "e2e", "pass",
                output=f"E2E: {len(pre_existing)} pre-existing failures on main (no new regressions)\n\n"
                       + e2e_output[:3000],
                stats=parse_test_output(e2e_output) if e2e_output else None,
            )
        e2e_output_header = (
            f"E2E: {len(new_failures)} NEW failures (+ {len(pre_existing)} pre-existing on main)\n"
            f"New failures: {', '.join(sorted(new_failures))}\n\n"
        )
        # Prepend header but keep the full output — gate_runner applies
        # smart_truncate_structured when writing to state, preserving the
        # numbered failure list.
        e2e_output = e2e_output_header + e2e_output

    result = GateResult(
        "e2e", "fail", output=e2e_output,
        stats=parse_test_output(e2e_output) if e2e_output else None,
    )
    scope = change.scope or ""
    # Point agent to failure screenshots in worktree
    screenshot_hint = ""
    wt_test_results = os.path.join(wt_path, "test-results")
    if os.path.isdir(wt_test_results):
        png_files = []
        for root, _dirs, files in os.walk(wt_test_results):
            for f in files:
                if f.endswith(".png"):
                    png_files.append(os.path.relpath(os.path.join(root, f), wt_path))
        if png_files:
            screenshot_hint = (
                f"\n\nFailure screenshots (READ these for visual context):\n"
                + "\n".join(f"- {p}" for p in png_files[:10])
            )

    # Preserve error-tail evidence: Playwright assertion errors and stack
    # traces appear near the end of stdout. A head-only slice drops them and
    # leaves the impl agent with only prisma setup noise to reason about.
    from set_orch.truncate import smart_truncate_structured
    result.retry_context = (
        f"E2E tests (Playwright) failed. Fix the failing E2E tests or the code they test.\n\n"
        f"E2E command: {e2e_command}\nE2E output:\n{smart_truncate_structured(e2e_output, 6000)}\n"
        f"{screenshot_hint}\n\n"
        f"Original scope: {scope}"
    )
    return result


# ─── Lint Helpers ────────────────────────────────────────────────────


def _load_forbidden_patterns(wt_path: str, profile=None) -> list[dict]:
    """Load forbidden patterns from profile plugin + project-knowledge.yaml."""
    patterns: list[dict] = []

    if profile is not None and hasattr(profile, "get_forbidden_patterns"):
        try:
            patterns.extend(profile.get_forbidden_patterns())
        except Exception:
            logger.warning("Failed to load forbidden patterns from profile", exc_info=True)

    pk_path = os.path.join(wt_path, "project-knowledge.yaml")
    if os.path.isfile(pk_path):
        try:
            import yaml
            with open(pk_path) as f:
                pk = yaml.safe_load(f) or {}
            fp = pk.get("verification", {}).get("forbidden_patterns", [])
            if isinstance(fp, list):
                patterns.extend(fp)
        except Exception:
            logger.warning("Failed to load forbidden_patterns from project-knowledge.yaml", exc_info=True)

    return patterns


def _is_comment_line(content: str) -> bool:
    """Check if a line is a code comment (should be skipped by lint)."""
    stripped = content.strip()
    # Single-line comments (JS/TS/Python/Shell)
    if stripped.startswith("//") or stripped.startswith("#"):
        return True
    # Block comment lines (JSDoc, multi-line comments)
    if stripped.startswith("*") or stripped.startswith("/**") or stripped.startswith("*/"):
        return True
    # Markdown-style documentation in code
    if stripped.startswith("- ") and "**" in stripped:
        return True
    return False


def _extract_added_lines(diff_output: str, skip_comments: bool = True) -> list[tuple[str, int, str]]:
    """Parse unified diff, return (file_path, approx_line, content) for added lines.

    When skip_comments=True (default), comment lines are excluded from results
    to prevent false positives when agents mention forbidden patterns in fix comments.
    """
    results: list[tuple[str, int, str]] = []
    current_file = ""
    current_line = 0

    for line in diff_output.split("\n"):
        if line.startswith("+++ b/"):
            current_file = line[6:]
            current_line = 0
        elif line.startswith("@@ "):
            match = re.search(r"\+(\d+)", line)
            if match:
                current_line = int(match.group(1)) - 1
        elif line.startswith("+") and not line.startswith("+++"):
            current_line += 1
            content = line[1:]
            if skip_comments and _is_comment_line(content):
                continue
            results.append((current_file, current_line, content))
        elif not line.startswith("-"):
            current_line += 1

    return results


# ─── Lint Gate Executor ──────────────────────────────────────────────


def execute_lint_gate(
    change_name: str, change: "Change", wt_path: str,
    profile=None,
) -> "GateResult":
    """Lint gate: deterministic grep-based forbidden pattern scanning."""
    from set_orch.gate_runner import GateResult
    from set_orch.subprocess_utils import run_git

    if not wt_path:
        return GateResult("lint", "pass")

    patterns = _load_forbidden_patterns(wt_path, profile)
    if not patterns:
        return GateResult("lint", "pass", output="no forbidden patterns configured")

    # Get merge base for diff
    from set_orch.verifier import _get_merge_base
    merge_base = _get_merge_base(wt_path)
    diff_result = run_git("diff", f"{merge_base}..HEAD", cwd=wt_path)
    if diff_result.exit_code != 0:
        return GateResult("lint", "pass", output="could not generate diff")

    added_lines = _extract_added_lines(diff_result.stdout)
    if not added_lines:
        return GateResult("lint", "pass")

    critical_matches: list[str] = []
    warning_matches: list[str] = []

    for pat_dict in patterns:
        pattern = pat_dict.get("pattern", "")
        severity = pat_dict.get("severity", "warning").lower()
        message = pat_dict.get("message", "")
        file_glob = pat_dict.get("file_glob", "")

        if not pattern:
            continue

        try:
            regex = re.compile(pattern)
        except re.error:
            logger.warning("Invalid forbidden pattern regex: %s", pattern)
            continue

        for file_path, line_num, content in added_lines:
            if file_glob and not fnmatch.fnmatch(file_path, file_glob):
                continue

            if regex.search(content):
                match_str = f"  File: {file_path} (line {line_num})\n  Pattern: {pattern}\n  Rule: {message}"
                if severity == "critical":
                    critical_matches.append(match_str)
                else:
                    warning_matches.append(match_str)

    if critical_matches:
        retry_ctx = "FORBIDDEN PATTERN(S) DETECTED:\n\n" + "\n\n".join(critical_matches)
        retry_ctx += "\n\nFix the root cause. Do NOT use type casts or workarounds to bypass."
        if warning_matches:
            retry_ctx += "\n\nWarnings (non-blocking):\n" + "\n".join(warning_matches)
        return GateResult(
            "lint", "fail",
            output=f"{len(critical_matches)} critical, {len(warning_matches)} warning pattern match(es)",
            retry_context=retry_ctx,
        )

    if warning_matches:
        return GateResult(
            "lint", "pass",
            output=f"{len(warning_matches)} warning pattern match(es):\n" + "\n".join(warning_matches),
        )

    return GateResult("lint", "pass")


# ─── i18n Completeness Gate ──────────────────────────────────────────


def _find_i18n_check_script(wt_path: str) -> str | None:
    for rel in ("scripts/check-i18n-completeness.ts", "scripts/check-i18n-completeness.mjs"):
        p = os.path.join(wt_path, rel)
        if os.path.isfile(p):
            return rel
    return None


def execute_i18n_check_gate(
    change_name: str, change: "Change", wt_path: str,
    profile=None,
) -> "GateResult":
    """i18n completeness check — ensures every `t('ns.key')` resolves in every locale.

    Skipped when:
      - no messages/ dir in worktree
      - no scripts/check-i18n-completeness.ts
      - no `useTranslations(` in src/

    Fast (~1-2s). Designed to pre-empt cascading Playwright failures that
    stem from a single missing translation key.
    """
    from set_orch.gate_runner import GateResult

    if not wt_path:
        return GateResult("i18n_check", "skipped", output="no worktree path")

    messages_dir = os.path.join(wt_path, "messages")
    if not os.path.isdir(messages_dir):
        return GateResult("i18n_check", "skipped", output="no messages/ directory")

    locale_files = [
        f for f in os.listdir(messages_dir)
        if re.fullmatch(r"[a-z]{2}(-[A-Z]{2})?\.json", f)
    ]
    if not locale_files:
        return GateResult("i18n_check", "skipped", output="no locale files in messages/")

    script_rel = _find_i18n_check_script(wt_path)
    if not script_rel:
        return GateResult("i18n_check", "skipped", output="no scripts/check-i18n-completeness.ts")

    src_dir = os.path.join(wt_path, "src")
    if not os.path.isdir(src_dir):
        return GateResult("i18n_check", "skipped", output="no src/ directory")

    uses_next_intl = False
    for root, _dirs, files in os.walk(src_dir):
        if "node_modules" in root or "/.next" in root:
            continue
        for f in files:
            if not f.endswith((".ts", ".tsx", ".js", ".jsx")):
                continue
            try:
                with open(os.path.join(root, f)) as fh:
                    content = fh.read(8192)
                if "useTranslations(" in content or "getTranslations(" in content:
                    uses_next_intl = True
                    break
            except OSError:
                continue
        if uses_next_intl:
            break

    if not uses_next_intl:
        return GateResult("i18n_check", "skipped", output="no useTranslations/getTranslations usage")

    # Resolve a runner: prefer local tsx, fall back to npx tsx.
    node_bin = os.path.join(wt_path, "node_modules", ".bin", "tsx")
    if os.path.isfile(node_bin):
        cmd = [node_bin, script_rel]
    else:
        cmd = ["npx", "--yes", "tsx", script_rel]

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd, cwd=wt_path, capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return GateResult(
            "i18n_check", "fail",
            output="i18n_check timed out after 30s",
            retry_context="i18n_check script timed out — inspect scripts/check-i18n-completeness.ts",
        )
    except FileNotFoundError:
        return GateResult("i18n_check", "skipped", output="tsx/npx not available")

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    output = (result.stdout or "") + (result.stderr or "")

    if result.returncode == 0:
        return GateResult(
            "i18n_check", "pass",
            output=output[:1500], duration_ms=elapsed_ms,
        )

    retry_ctx = (
        "i18n completeness check failed — one or more translation keys referenced in "
        "the code have no entry in messages/<locale>.json. Missing keys cause cascading "
        "Playwright failures (hydration errors, runtime MISSING_MESSAGE). Fix: add the "
        "missing keys listed below to every locale file, mirroring the key set.\n\n"
        + output[:4000]
    )
    return GateResult(
        "i18n_check", "fail", output=output[:4000],
        retry_context=retry_ctx, duration_ms=elapsed_ms,
    )
