## Context

The orchestration pipeline has three testing layers: pre-merge Jest (`test_command`), pre-merge Playwright (`e2e_command`), and post-merge smoke (`smoke_command`). Both Playwright paths run tests but discard all visual artifacts. Playwright automatically generates screenshots on failure in `test-results/`, and can be configured for screenshots on every test — but the orchestrator never collects these.

The smoke pipeline runs on main after merge. In checkpoint mode (`checkpoint_every: 3`), multiple changes merge before smoke runs. If smoke fails, the fix agent receives context only about the last change — but the failure may be caused by an interaction between changes.

Currently, already-merged changes (from previous orchestration phases) get `smoke_result: null` because the "already merged" path in `merger.sh` skips the entire post-merge pipeline.

## Goals / Non-Goals

**Goals:**
- Collect Playwright `test-results/` artifacts after every smoke and per-change E2E run
- Store artifacts in deterministic paths for report linking
- Display screenshot galleries in the HTML report
- Provide multi-change context to the smoke fix agent after checkpoint merges
- Set explicit `smoke_result: "skip"` for already-merged changes

**Non-Goals:**
- Visual regression testing (pixel-level diff between screenshots) — future work
- Changing which test framework runs as smoke (that's a config decision per project)
- Modifying the phase-end E2E pipeline (already has screenshot collection)
- Adding screenshot support to Jest (Jest doesn't produce visual artifacts)

## Decisions

### 1. Artifact storage paths

```
wt/orchestration/
├── smoke-screenshots/
│   ├── cart-discounts-promo/       # per change
│   │   ├── attempt-1/             # first run (fail)
│   │   │   ├── checkout-page.png
│   │   │   └── ...
│   │   └── attempt-2/             # fix retry (pass)
│   │       └── checkout-page.png
│   └── auth-login-register/
│       └── attempt-1/
├── e2e-screenshots/
│   ├── cart-discounts-promo/       # per change (from worktree)
│   │   ├── test-results/...
│   │   └── ...
│   └── cycle-0/                   # phase-end (existing)
```

**Rationale**: Separate directories for smoke vs e2e because they run at different stages (post-merge vs pre-merge). Change name as directory key because that's the natural grouping. Smoke uses `attempt-N/` subdirectories to preserve both failure and fix screenshots — the failure screenshots are the most diagnostic for understanding what broke, while the pass screenshots confirm the fix. This mirrors the existing `cycle-N` pattern used by phase-end E2E.

### 2. Artifact collection mechanism

```bash
# After smoke command completes (pass or fail):
# Determine attempt number from smoke_fix_attempts (0 = first run)
local attempt_num
attempt_num=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .smoke_fix_attempts // 0' "$STATE_FILENAME")
local sc_dir="wt/orchestration/smoke-screenshots/$change_name/attempt-$((attempt_num + 1))"
mkdir -p "$sc_dir"
if [[ -d "test-results" ]]; then
    cp -r test-results/* "$sc_dir/" 2>/dev/null || true
fi
local sc_count
sc_count=$(find "wt/orchestration/smoke-screenshots/$change_name" -name "*.png" 2>/dev/null | wc -l)
update_change_field "$change_name" "smoke_screenshot_dir" "\"wt/orchestration/smoke-screenshots/$change_name\""
update_change_field "$change_name" "smoke_screenshot_count" "$sc_count"
```

**Rationale**: Same pattern as the existing phase-end E2E collection in `verifier.sh:544-553`. Uses `cp -r` with `|| true` to avoid failures on empty directories. Counts only `.png` files (Playwright's default screenshot format). Uses `attempt-N/` subdirectories so failure screenshots are preserved alongside fix screenshots — the failure shots are the most diagnostic for understanding what broke.

**Alternative considered**: Overwriting on fix retry — rejected because failure screenshots are the most valuable diagnostic artifacts and should not be lost when the fix agent succeeds.

**Alternative considered**: Moving instead of copying — rejected because the test-results may be needed by subsequent pipeline steps or for debugging.

### 2a. Hardcoded `test-results/` path

The Playwright artifact directory is hardcoded to `test-results/` (Playwright's default `outputDir`). This is a conscious decision: projects that customize `outputDir` in `playwright.config.ts` are an edge case, and adding a directive for this would be over-engineering. If needed in the future, a `playwright_output_dir` directive can be added to `orchestration.yaml`.

### 3. Per-change E2E: copy from worktree to main project

The per-change E2E runs in an isolated worktree. Artifacts must be copied to the main project's `wt/orchestration/` directory.

```bash
# In verifier.sh after per-change E2E:
local e2e_sc_dir="wt/orchestration/e2e-screenshots/$change_name"
mkdir -p "$e2e_sc_dir"
if [[ -d "$wt_path/test-results" ]]; then
    cp -r "$wt_path/test-results/"* "$e2e_sc_dir/" 2>/dev/null || true
fi
```

**Rationale**: The worktree gets cleaned up after merge, so artifacts must be saved beforehand. Using absolute path to worktree's `test-results/` since the working directory is the main project during verify gate.

### 4. Multi-change smoke context via `last_smoke_pass_commit`

Track the HEAD commit SHA after each successful smoke. On failure, use it to find all changes merged since:

```bash
# On smoke pass (ONLY after an actual smoke run, not on init):
update_state_field "last_smoke_pass_commit" "\"$(git rev-parse HEAD)\""

# On smoke fail (in fix prompt):
local since_commit
since_commit=$(jq -r '.last_smoke_pass_commit // ""' "$STATE_FILENAME")
if [[ -n "$since_commit" ]]; then
    local merged_since
    merged_since=$(git log --oneline "$since_commit..HEAD" --merges)
    # Include in fix prompt
fi
# If last_smoke_pass_commit is empty (no smoke has passed yet),
# skip multi-change context — fall back to single-change context only.
```

**Rationale**: Using git SHAs is reliable because the orchestrator operates on the main branch linearly. The merge commits in `git log --merges` map directly to change names. This avoids maintaining a separate counter or list in state.json.

**Cold start**: `last_smoke_pass_commit` is initialized to empty string `""`, NOT to the current HEAD. It is only set after the first actual smoke pass. This prevents a false positive where orchestration starts with a broken main — if initialized to HEAD, the first smoke failure would blame all changes merged so far, even though the regression was pre-existing. With empty init, the first failure gets single-change context only (existing behavior), and multi-change context kicks in only after a known-good baseline exists.

**Alternative considered**: Initializing to HEAD at orchestration start — rejected because it creates false multi-change blame when main is already broken at start.

**Alternative considered**: Tracking a list of change names in state.json — rejected as redundant with git history and would need manual cleanup.

### 5. Reporter screenshot display

```
Execution table:
| Change | Status | ... | E2E | Smoke |
|--------|--------|-----|-----|-------|
| cart   | merged |     | ✓📷 | ✓📷  |  ← camera icon = has screenshots
| auth   | merged |     | ✓   | ✓    |  ← no camera = no screenshots
| old    | merged |     | -   | skip |  ← skip for previous phase

Expandable gallery below table:
▸ Smoke Screenshots (12 images)
  [cart-discounts: 8 images]  [auth-login: 4 images]
```

Camera icon links to the screenshot directory. Gallery is collapsible `<details>` to avoid bloating the report. Group by change name, max 8 images per change to keep the report responsive. Per-change cap instead of global cap — with checkpoint mode (`checkpoint_every: 3`), a global cap of 20 would cut off the third change entirely.

### 6. Already-merged skip status

In `merger.sh` lines 59-69 (Case 1: branch deleted) and 75-85 (Case 2: already ancestor), add:

```bash
update_change_field "$change_name" "smoke_result" '"skip_merged"'
update_change_field "$change_name" "smoke_status" '"skipped"'
```

**Rationale**: Explicit skip is better than null — the reporter can display "skip" with a tooltip explaining why, and no data is ambiguous. Uses `"skip_merged"` instead of `"skip"` because `"skip"` is already used when no `smoke_command` directive is configured. The reporter needs to distinguish between "no smoke configured" (skip) and "already merged from previous phase" (skip_merged) to show different tooltips.

## Risks / Trade-offs

- **Disk space**: Playwright screenshots are ~50-200KB each. 20 changes × 10 screenshots = ~20-40MB per orchestration run. Acceptable. The `wt/orchestration/` directory is ephemeral per run.
  → Mitigation: Max 20 images displayed in report gallery. Old run artifacts are cleared on orchestration restart.

- **Smoke command is Jest, not Playwright**: If `smoke_command` runs Jest, there's no `test-results/` directory and no screenshots. The collection code handles this gracefully (0 count, empty dir).
  → Mitigation: Documentation should recommend Playwright for smoke_command. The feature works correctly regardless — it just produces no artifacts for non-Playwright test runners.

- **Worktree cleanup race**: Per-change E2E artifacts must be collected before the worktree is cleaned up in the merge pipeline.
  → Mitigation: Collection happens immediately after the E2E gate, before the change enters the merge queue. The worktree is only cleaned up during `merge_change()`.

- **Multi-change context prompt size**: Including git log and file diffs for 3+ changes may push the fix prompt too large.
  → Mitigation: Truncate git log to `--oneline` and limit to last 500 chars. The change names are the most valuable context; full diffs are secondary.
