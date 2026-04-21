## Context

`execute_e2e_gate` in `modules/web/set_project_web/gates.py` runs Playwright directly via `run_command(["bash", "-c", actual_e2e_cmd], cwd=wt_path, env=e2e_env, …)` at line 618. It assumes `node_modules/` in the worktree matches the committed `package.json`. This assumption breaks when:

1. The agent edits `package.json` to add a dependency (e.g. `dotenv`)
2. The agent commits without running `pnpm install`
3. Playwright loads `playwright.config.ts`, tries `require("dotenv/config")`, Node throws `MODULE_NOT_FOUND`
4. Playwright exits 1 without emitting a parseable failure list
5. The gate falls into the `gates.py:760` "no parseable failure list" branch and marks a real retry attempt

Observed cost (craftbrew-run-20260421-0025 foundation-setup, attempt 3→4): ~4 minutes wall-clock + 1 of 4 `verify_retry_count` slots + full agent session resume (~21 k tokens) + pnpm install + prisma generate + seed + full e2e rerun — for a fix that was literally `pnpm install`.

Existing install triggers and why they do not cover this:
- `_reinstall_deps_if_needed` (`lib/set_orch/dispatcher.py:298`) — only on main↔worktree sync (diff between merge-base and main HEAD, not agent's own commits)
- `_post_merge_deps_install` (`lib/set_orch/merger.py:2640`) — only at integration gate time after merge, which never happens for a failing change

The `ProjectType` ABC already exposes the primitives we need: `detect_package_manager(wt_path)`, `detect_dep_install_command(wt_path)`. No new abstraction required.

## Goals / Non-Goals

**Goals:**
- Eliminate wasted retry attempts when the failure is only a missing-dep install, not real test failure.
- Keep the fast path fast: zero extra work when `node_modules/` is already in sync with `package.json`.
- Localize the fix to Layer 2 (web plugin) — no core or template changes.
- Emit clear forensic signals (`e2e_deps_drift_detected`, `e2e_self_heal_installed_and_rerun`) so post-run analysis can tell self-healed runs from real ones.

**Non-Goals:**
- Not a generalized "install-before-any-gate" mechanism. Only applies to the verify e2e gate in the web module. If a python-web project-type eventually appears, it implements its own.
- Not prevention of the agent's bad habit (agents should still run `pnpm install` after modifying `package.json`). This is a gate-level safety net, not behavior correction.
- Not a replacement for `_reinstall_deps_if_needed` or `_post_merge_deps_install`. Those still run in their respective phases.
- Not retry the e2e more than once in-gate. If install + one rerun still fails, the gate returns fail as it does today and a real retry attempt is consumed.

## Decisions

### Decision 1: Two-level defense — pre-check AND self-heal

**Chosen**: implement both the pre-gate drift check (proactive, cheap) AND the post-fail self-heal (reactive, catches edge cases).

**Why both**:
- Pre-check catches the common case (agent modified package.json, committed, never ran install) before Playwright even boots. Saves the whole webServer startup + crash cycle (~30-40s on craftbrew).
- Self-heal catches edge cases the mtime check misses: e.g. a merged lockfile from main changed transitive deps, `node_modules/.modules.yaml` got touched by a stray pnpm invocation in another worktree, or a stale cache where mtime lies.
- Total cost: one warm-cache `pnpm install` (~1-2 s) when drift is detected, zero when fresh.

**Alternative rejected**: only self-heal. Cheaper to implement but costs ~40 s of webServer boot + Playwright crash on every drift event. Not worth it given how trivial the pre-check is.

**Alternative rejected**: only pre-check. Misses the transitive-dep edge case (package.json unchanged but a transitive dep is missing from node_modules). Self-heal covers this via the MODULE_NOT_FOUND regex even when the missing package is a sub-dep.

### Decision 2: mtime comparison as the drift signal

**Chosen**: compare `os.path.getmtime(package.json)` to `os.path.getmtime(node_modules/.modules.yaml)` (pnpm) / `node_modules/.package-lock.json` (npm). If `package.json` is newer, drift.

**Why**: pnpm writes `.modules.yaml` at the end of install. npm writes `.package-lock.json` copy. Both reliably mark "last successful install". Simple, no extra I/O beyond two stat calls.

**Alternatives rejected**:
- **SHA fingerprint of package.json vs stored last-install SHA**: more correct but requires persisting a new piece of state. Overkill for a safety net.
- **`pnpm install --frozen-lockfile --dry-run`**: authoritative but 200-400 ms and spawns a subprocess on every gate run even when clean.
- **Check node_modules existence only**: too weak — node_modules exists from `set-new` scaffold but lacks new deps.

**Risk**: mtime can be rewritten by git checkout, unrelated tools, etc. → Mitigation: this is a "false positive leads to one extra install" failure mode, cheap. False negative (drift not detected) is caught by the self-heal.

### Decision 3: Self-heal regex and scope

**Chosen**: on the unparseable-fail branch, check `re.search(r"Cannot find module '([^']+)'", e2e_output)` AND `"MODULE_NOT_FOUND"` in output. Extract the first path segment of the captured module name (`"dotenv/config"` → `"dotenv"`). If that package is declared in `package.json` (top-level in `dependencies` or `devDependencies`), self-heal.

**Why constrain to declared packages**: prevents self-heal from running `pnpm install` on a typo like `Cannot find module './doesnotexist'` or an application-code bug. If the module is not declared, that IS the bug — bubble up.

**Alternatives rejected**:
- **Install unconditionally on any MODULE_NOT_FOUND**: would "fix" genuine user bugs by masking them with a rerun. No — only when declared-but-missing.
- **Check transitive deps too (pnpm-lock.yaml)**: expensive to parse. The package.json check covers the 95 % case; the remaining 5 % is why we run `pnpm install` (which will resolve transitive deps as a side-effect anyway).

### Decision 4: In-gate retry does NOT consume `verify_retry_count`

**Chosen**: the self-heal path runs `pnpm install` + reruns e2e inside `execute_e2e_gate`. If the rerun passes, return GateResult pass as normal. If rerun fails, return fail — this consumes a retry attempt (same as today).

**Why**: the whole point is to avoid spending a retry slot on a mechanical infrastructure issue. If it's really broken after install, we want the normal retry flow to take over with real diagnostics.

**Alternative rejected**: always consume a slot but log `self_heal_attempted`. Conservative but defeats the purpose.

### Decision 5: Scope — web module only (Layer 2), no core touch

**Chosen**: put everything in `modules/web/set_project_web/gates.py`. Use existing `ProjectType.detect_package_manager()` / `detect_dep_install_command()` ABC methods — no new ABC surface.

**Why**: per `.claude/rules/modular-architecture.md` rule #1 (no JS specifics in core) and rule #2 (extension point is the profile). The mtime semantics (`.modules.yaml`, `.package-lock.json`) and the regex (`MODULE_NOT_FOUND`) are Node/JS specific. If a future python-web profile needs the same mechanism, it adds its own version.

**Alternative rejected**: add `ProjectType.ensure_deps_synced(wt_path) -> bool` to the ABC now. Premature abstraction (YAGNI) — second implementation doesn't exist yet. Can refactor later when there's a second consumer.

## Risks / Trade-offs

- **[False negative: pre-check misses transitive drift]** → Mitigated by self-heal on MODULE_NOT_FOUND.
- **[False positive: mtime drift without real need to install]** → Runs one extra `pnpm install`. Warm cache cost is ~1-2 s. Accepted.
- **[Self-heal masks a real bug where dep genuinely shouldn't be installed]** → Constrained by "declared in package.json" check; if declared, install is the correct response.
- **[Self-heal rerun also crashes]** → Same as today — returns fail, normal retry flow takes over, `verify_retry_count` increments.
- **[Install subprocess hangs / times out]** → Bound install timeout to 120 s (same as `_reinstall_deps_if_needed`). On timeout, skip self-heal and fall through to normal fail.
- **[Concurrent e2e gates racing on node_modules/]** → `pnpm install` is safe under concurrent access; pnpm uses a lockfile-based lock inside `~/.local/share/pnpm/`. Accepted.
- **[Forensics ambiguity between real pass and self-healed pass]** → Mitigated by explicit INFO log events and embedding `[self-heal: installed <pkg>]` marker in GateResult.output so `set-run-logs` can surface it.

## Migration Plan

1. Implement `_ensure_deps_synced(wt_path, profile)` and `_self_heal_missing_module(wt_path, profile, e2e_output)` helpers in `modules/web/set_project_web/gates.py`.
2. Wire pre-check at the top of `execute_e2e_gate` right before `_kill_stale_listeners_on_port`.
3. Wire self-heal on the `if not wt_failures:` branch (`gates.py:760`) before returning the fail GateResult.
4. Unit tests in `modules/web/tests/test_gates_dep_drift.py`.
5. No consumer redeploy needed — web module loads from the same venv.
6. Rollback: single file revert on `gates.py`. No persisted state, no migration.

## Open Questions

None. Scope is self-contained and reversible.
