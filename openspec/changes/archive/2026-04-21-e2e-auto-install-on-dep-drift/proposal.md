## Why

When an agent adds a new npm dependency to `package.json` but does not run `pnpm install` before committing, the worktree has a declared-but-not-installed dep. The verify e2e gate invokes `playwright test` directly; Playwright fails to load `playwright.config.ts` (e.g. `import "dotenv/config"` → `Cannot find module 'dotenv/config' … MODULE_NOT_FOUND`) and the gate reports "crash/OOM/formatter issue" because there is no parseable failure list.

Craftbrew run `craftbrew-run-20260421-0025` foundation-setup hit this on attempt 3: one retry slot and ~4 minutes wall-clock were spent restarting the agent session, pnpm-installing, prisma-generating, seeding, and rerunning e2e — when the *only* thing that needed to happen was `pnpm install`. No new phase attempt was required.

Install is currently triggered in two places, neither of which covers this gap:
- `_reinstall_deps_if_needed` (`lib/set_orch/dispatcher.py:298`) — only on main↔worktree sync
- `_post_merge_deps_install` (`lib/set_orch/merger.py:2640`) — only after merge, at integration gate time

The agent's own worktree commits can drift `package.json` from `node_modules/` without any install trigger until merge — which only happens if verify passes.

## What Changes

- Add a **pre-e2e dep-drift check** inside `execute_e2e_gate` (`modules/web/set_project_web/gates.py`): before running Playwright, compare `package.json` mtime against the package-manager install marker (pnpm: `node_modules/.modules.yaml`, npm: `node_modules/.package-lock.json`). On drift → run `profile.detect_dep_install_command()` in the worktree. Fast no-op on warm cache.
- Add a **self-heal retry** on the "no parseable failure list" path (`gates.py:760-781`): regex-match `Cannot find module '([^']+)'` + `MODULE_NOT_FOUND` in e2e output. If the missing package is declared in `package.json`, run install, rerun e2e once **in-gate** (no `verify_retry_count` increment, no agent session resume).
- Instrument both paths with INFO-level logs (module name, install duration, rerun outcome) so forensics can distinguish "gate self-healed" from "real failure".
- No core (Layer 1) changes. No template changes. Entirely Layer 2 (`modules/web/set_project_web/gates.py`) using existing `ProjectType.detect_package_manager()` / `detect_dep_install_command()` abstractions.
- No consumer redeploy — the running sentinel loads the profile from the same venv, so next orchestration run picks it up.

## Capabilities

### New Capabilities
- `e2e-dep-drift-guard`: Pre-gate and in-gate dep-install logic that prevents and self-heals `MODULE_NOT_FOUND` crashes caused by `package.json` drift from `node_modules/` in a worktree.

### Modified Capabilities
<!-- none — web-gates covers baseline/port behavior, this is new territory -->

## Impact

- **Code**: `modules/web/set_project_web/gates.py` (add `_ensure_deps_synced` helper, integrate into `execute_e2e_gate`; add `_is_missing_module_crash` + self-heal branch on unparseable-fail).
- **Tests**: unit tests for drift detection (mtime comparison), regex match, package.json lookup; integration test via `tests/integration/` with a fabricated worktree that has package.json ahead of node_modules.
- **Retry budget**: self-heal does NOT consume `verify_retry_count`, keeping the 4-attempt budget for real failures.
- **Logs**: new INFO events `e2e_deps_drift_detected`, `e2e_dep_install_completed`, `e2e_self_heal_installed_and_rerun`. Forensics and `set-run-logs` will show these.
- **Behavior invariance**: when `node_modules` is fresh (mtime ≥ `package.json`), no extra work runs — zero overhead for the common case.
- **Dependencies**: relies on `profile.detect_package_manager()` and `profile.detect_dep_install_command()` (already in `ProjectType` ABC since `worktree-deps-sync`).
