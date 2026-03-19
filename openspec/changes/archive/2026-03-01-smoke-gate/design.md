## Architecture

The smoke gate adds two test execution points to the orchestration pipeline:

1. **Local smoke** (verify gate Step 2c) — runs `smoke_command` in the worktree with a dev server. Blocking: if it fails, the agent gets retried with the smoke output. Positioned after build (cheap) but before LLM review (expensive) to save tokens.

2. **Deploy smoke** (post-merge) — after merge+push, polls `deploy_smoke_url + deploy_healthcheck` until healthy, then runs `smoke_command` with `SMOKE_BASE_URL` env var. Advisory: failure sends notification but doesn't block other changes.

## Gate Pipeline (Updated)

```
handle_change_done():
  Step 1:  test_command (unit)           ← existing
  Step 2:  build                         ← existing
  Step 2b: test file check               ← existing (warning only)
  Step 2c: smoke_command (local)         ← NEW — e2e against localhost
  Step 3:  LLM review                    ← existing
  Step 4:  /opsx:verify                  ← existing
  Step 5:  merge + push                  ← existing
  Step 6:  deploy smoke                  ← NEW — e2e against deployed URL
```

## Directive Integration

Four new directives added to the existing precedence chain (CLI > YAML > in-doc > defaults):

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `smoke_command` | string | `""` (disabled) | Command to run smoke tests |
| `smoke_timeout` | int | `120` | Timeout in seconds for smoke tests |
| `deploy_smoke_url` | string | `""` (disabled) | Remote URL for post-merge smoke |
| `deploy_healthcheck` | string | `/api/health` | Health endpoint to poll before deploy smoke |

## Local Smoke Execution

### DB Isolation Problem

All worktrees share the same `DATABASE_URL` (copied from `.env` by `bootstrap_worktree()`). The smoke `globalSetup` runs `prisma db push --force-reset` + `prisma db seed` to get clean state. With `max_parallel=2+`, two smoke gates running simultaneously would destroy each other's DB.

### Solution: flock serialization

The orchestrator wraps smoke execution in `flock` to ensure only one smoke gate runs at a time:

```bash
flock --timeout 180 /tmp/wt-smoke-gate.lock bash -c "
  cd '$wt_path' && timeout '$smoke_timeout' bash -c '$smoke_command'
"
```

This means:
- Smoke gates are serialized — only 1 runs at a time, others wait (max 180s timeout)
- All other gate steps (test, build, review, verify) remain parallel
- The smoke is ~30-60s, so the wait is typically short
- The agent is already "done" when smoke runs — no dev server conflict in the worktree

The project's `globalSetup` handles the DB reset+seed. The orchestrator just ensures serialized execution.

State field: `smoke_result` (pass/fail/skip), `smoke_output` (truncated), `gate_smoke_ms`.

## Deploy Smoke Execution

Runs after successful merge, in the project root (not worktree — already cleaned up):

```bash
# 1. Poll healthcheck
for i in {1..30}; do
    curl -sf "${deploy_smoke_url}${deploy_healthcheck}" && break
    sleep 10
done

# 2. Run smoke against deployed URL
SMOKE_BASE_URL="$deploy_smoke_url" timeout "$smoke_timeout" bash -c "$smoke_command"
```

On failure: `send_notification` with advisory level — does not block other changes or trigger retry. The merge is already done.

State field: `deploy_smoke_result` (pass/fail/skip).

## Decomposition Prompt Guidance

Add to both spec-mode and brief-mode decomposition prompts:

> If `smoke_command` is configured, changes that modify user-facing flows (login, navigation, forms, API endpoints) should include smoke test updates for affected functionality groups.

## Planning Guide Addition

Add a section on smoke test coverage:

> When a project has `smoke_command` configured, the planner should ensure changes that affect user-facing flows include smoke test creation or updates as part of the change scope. Organize smoke tests by functional group (auth, CRUD, navigation) not by change.

## TUI Impact

Add `S` indicator to gate display for smoke status, following the existing T/B/R/V pattern.

## DB Isolation: Why flock, Not Per-Worktree DBs

Alternative considered: create a separate database per worktree (`sales_raketa_${change_name}`). Rejected because:
- Requires `createdb` + `prisma migrate deploy` + `prisma db seed` per worktree (~30s overhead per dispatch)
- Cleanup needed after worktree removal
- Some projects have hardcoded DB references
- The smoke gate already runs after the agent is done — no parallel access conflict within one worktree
- Serialization also avoids overloading the machine with multiple Playwright+dev server instances simultaneously

## Not In Scope

- Playwright setup/scaffolding — project-specific, not set-core responsibility
- CI/CD webhook integration — too platform-specific
- Auto-detection of smoke test framework — explicit directive only
- Per-worktree database isolation — flock serialization is simpler and sufficient
