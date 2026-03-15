## Context

The orchestration pipeline has a blind spot: it trusts agent self-reporting without verifying worktree cleanliness. In practice this means an agent can write files, never commit them, and still pass the done-check and verify gate. Additionally, agents dispatched to worktrees mid-project lack context on how to start the application — there's no canonical "getting started" section in the worktree's CLAUDE.md. Finally, the smoke_command defaults to `pnpm test` which only runs mocked unit tests and misses build/type errors.

**Current state:**
- `loop_tasks.is_done()` checks task checkboxes or test exit code — never worktree cleanliness
- `verifier.handle_change_done()` runs build → test → e2e → scope → review → rules → verify → merge — no uncommitted check
- `dispatcher.dispatch_change()` copies artifacts to worktree but doesn't write startup documentation
- `config.auto_detect_test_command()` detects `pnpm test` / `npm test` — no separate smoke resolution
- `smoke_command` in orchestration.yaml is empty by default; when set, it's a single command string

## Goals / Non-Goals

**Goals:**
- Prevent false-positive done-checks when agent has uncommitted work
- Give agents entering worktrees clear instructions on how to run the app and tests
- Make smoke verification catch build errors by default (build + test, not just test)

**Non-Goals:**
- Changing the gate-profiles system (separate change handles which gates run per change type)
- Forcing agents to commit — the guard detects and blocks, the agent decides how to fix
- Auto-generating startup docs from code analysis — the guide is maintained by infrastructure/foundational changes and the dispatcher

## Decisions

### D1: Uncommitted work check as a utility function

Create `git_has_uncommitted_work(wt_path) -> tuple[bool, str]` in a shared location (`lib/wt_orch/git_utils.py` or inline in `loop_tasks.py`). It runs:
```
git -C <wt_path> status --porcelain
```
If output is non-empty, there are uncommitted changes. The string return contains the summary (e.g., "3 modified, 7 untracked").

**Why not `git diff`?** `--porcelain` catches both staged, unstaged, AND untracked files in one call. `git diff` misses untracked files.

**Alternative considered:** Check only for tracked modified files (ignore untracked). Rejected because the exact failure case in the latest run was 7 *new untracked* files that were never committed.

### D2: Guard placement — both loop done-check AND verify gate

The uncommitted work check runs in two places:
1. **`is_done()` pre-check** — before any done_criteria evaluation. If uncommitted work exists, return False immediately. This prevents the Ralph loop from stopping too early.
2. **`handle_change_done()` first gate step** — before VG-BUILD. If uncommitted work exists, fail the verify with a descriptive message and trigger retry (the agent gets re-dispatched and sees the message).

**Why both?** The loop done-check is the first line of defense (agent stays in loop). The verify gate is the second (catches cases where loop state was manually set or the agent exited abnormally).

**Exclusion:** `done_criteria == "manual"` skips the uncommitted check — manual tasks may legitimately have no code changes.

### D3: Startup guide — dispatcher writes to CLAUDE.md

On dispatch, the dispatcher reads the current project state and appends an `## Application Startup` section to the worktree's CLAUDE.md (if it doesn't already have one). The content comes from:

1. **Template defaults** (from wt-project-web planning_rules): dev server command, DB setup pattern
2. **Runtime detection**: package manager, framework (Next.js/Vite/etc.), DB (Prisma/Drizzle)
3. **Existing state**: if prior changes have already set up infrastructure, the guide reflects that

The section is idempotent — if `## Application Startup` already exists in CLAUDE.md, don't overwrite it.

**Why CLAUDE.md?** It's the canonical file that agents read on entry. Rules files are glob-scoped and may not trigger for all file types. CLAUDE.md is always loaded.

**Alternative considered:** A separate `STARTUP.md` file. Rejected because agents already read CLAUDE.md automatically — a separate file requires explicit instructions to read it.

### D4: Build-inclusive smoke resolution

Add `auto_detect_smoke_command(directory)` to `config.py`:
1. If `orchestration.yaml` has explicit `smoke_command`, use it (existing behavior)
2. If not, detect: if build script exists (`build` or `build:ci` in package.json), prepend it: `<pm> run build && <pm> test`
3. If no build script, fall back to test_command

This doesn't change the existing `smoke_command` config — it only changes the *default* when smoke_command is empty.

## Risks / Trade-offs

- **[Risk] False-negative on uncommitted check** — agent intentionally leaves scratch files uncommitted (e.g., debug logs). → Mitigation: The uncommitted check only applies to done-check and verify gate, not during active iteration. The agent has time to clean up before declaring done. The message tells the agent exactly what's uncommitted.
- **[Risk] Startup guide gets stale** — infrastructure changes update the app but the guide section isn't refreshed. → Mitigation: The guide is only written on first dispatch (idempotent — if section already exists, skip). Staleness is addressed by planning rules: infrastructure/foundational changes MUST update the section as part of their task scope. This keeps the agent (not the dispatcher) responsible for accuracy.
- **[Risk] Build step in smoke adds latency** — `pnpm build` can take 30-60s. → Mitigation: This only affects smoke_command (post-done), not the fast test_command loop. The extra 30s is worth catching type errors that mocked tests miss.
- **[Risk] `git status --porcelain` slow on large repos** — → Mitigation: `--porcelain` is fast even on large repos. We already run git commands in many places. Add a 10s timeout as safety.

## Open Questions

- Should the uncommitted guard have a config flag to disable it (`skip_uncommitted_check`)? Leaning no — if an agent has uncommitted work and claims done, that's always a bug.
