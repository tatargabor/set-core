## Why

The verify/merge pipeline has four compounding problems discovered during E2E runs:

1. **E2E gate runs ALL tests, not just change-scoped ones.** When 71/72 Playwright tests pass but 1 unrelated test fails, the entire change is marked failed after 2 retries. This wastes agent tokens and blocks valid changes.

2. **E2E port allocation is broken.** The "manual server" path picks a random port and health-checks it, but nobody starts a dev server on that port. Playwright's `webServer` config handles this correctly — the manual path should be removed.

3. **Post-merge smoke/build/scope checks are redundant.** After integration merge (main→worktree) + verify gate pass, the ff-only merge to main produces identical code. Running smoke tests on main is pure waste.

4. **Decomposer creates too many small changes.** 7 bugs became 15 changes because the decomposer treats each requirement as a separate change. Small bugfixes in the same domain should be grouped into a single change.

## What

1. **E2E gate scoping**: Run only tests affected by the change (based on changed files → test file mapping), or compare against main baseline to filter pre-existing failures.

2. **E2E server cleanup**: Remove random port allocation. Rely on Playwright's webServer config. If no webServer configured, skip E2E with a clear diagnostic message.

3. **Post-merge simplification**: Remove smoke pipeline, scope verify, and build check from post-merge. Keep only: deps install, custom command, plugin directives, i18n sidecar merge.

4. **Decomposer grouping**: Add domain-based grouping heuristic to the decompose prompt. Small-complexity changes (S) in the same domain/directory should be merged into a single change. Target change count should respect max_parallel.

## Scope

- `lib/set_orch/verifier.py` — E2E gate: baseline comparison, remove manual port path
- `lib/set_orch/merger.py` — Remove post-merge smoke pipeline, scope verify
- `lib/set_orch/templates.py` — Decomposer prompt: grouping heuristic for small changes
- `lib/set_orch/gate_runner.py` — E2E baseline comparison support (if needed)
