# Quality Gates

## Overview

When a Ralph loop finishes its work (`loop-state.status == "done"`), the change is not immediately merged. It must pass through a sequential quality pipeline where every "gate" checks a different aspect of the work.

![The sequential quality gates pipeline](diagrams/rendered/07-verification-gates.png){width=95%}

## Test Gate

The first and most important gate. If a `test_command` is configured, the system runs tests in the worktree.

### How It Works

```bash
# The verifier.sh run_tests_in_worktree() function:
cd <worktree_path>
timeout <test_timeout> bash -c "<test_command>"
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `test_command` | "" (skip) | The test command to run |
| `test_timeout` | 300s | Timeout for test execution |

### Output Handling

- **Pass** (exit code 0): Proceed to the next gate
- **Fail** (non-zero exit code): The test output (max 2000 characters) is saved, and the change goes back to the Ralph loop with the error message as retry context

Test statistics (`test_stats`) are saved to the state file:

```json
{
  "test_result": "pass",
  "test_stats": {
    "exit_code": 0,
    "duration_ms": 12500,
    "output_tail": "Tests: 42 passed, 42 total"
  }
}
```

## Review Gate

LLM-based code review, performed by a (typically) smaller and faster model.

### How It Works

The system:

1. Collects the modifications made in the change (`git diff`)
2. Adds the change scope and assigned requirements
3. Sends it to the `review_model` (default: sonnet)
4. The LLM evaluates code quality

### Requirement-Aware Review

`build_req_review_section()` appends the relevant requirements to the review prompt:

```
## Assigned Requirements (this change owns these)
- REQ-001: JWT authentication — Token-based auth on /api/* endpoints
- REQ-004: Token refresh — Automatic refresh of expired tokens

## Cross-Cutting Requirements (awareness only)
- REQ-012: Logging — Log all API calls
```

This helps the LLM evaluate not just code quality, but **requirement compliance** as well.

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `review_before_merge` | false | Enable review gate |
| `review_model` | opus | Model used for review |
| `skip_review` | false | Change-level skip (in plan) |

## Verify Gate

The verify gate checks whether the implementation matches the scope.

### How It Works

The `verify_merge_scope()` function:

1. Compares the planned scope with actual modifications
2. Checks that essential changes were made
3. Identifies unwanted side effects (scope creep)

### Strict Sentinel Mode

The verify gate requires a `VERIFY_RESULT: PASS` or `VERIFY_RESULT: FAIL` sentinel line in the agent output. If the sentinel is missing, the gate fails (strict mode) — there is no heuristic fallback. This prevents silent false passes when the verify skill crashes or produces incomplete output.

### Retry Logic

If the verify gate fails:

```
verify_retry_count < max_verify_retries?
  → yes: retry_context + Ralph loop restart
  → no: change → failed
```

The retry context includes the verify error message, build output, and original scope, so the agent can fix the problem in a targeted way.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_verify_retries` | 2 | Maximum retry count |

## Smoke Gate

The smoke test is a lightweight, fast check that verifies build integrity.

### How It Works

```bash
cd <worktree_path>
timeout <smoke_timeout> bash -c "<smoke_command>"
```

### Blocking vs Non-blocking

| Mode | Behavior |
|------|----------|
| `smoke_blocking: true` | Failed smoke → Ralph retry (fix cycle) |
| `smoke_blocking: false` | Failed smoke → warning, but merge allowed |

### Smoke Fix Cycle

If the smoke test fails and `smoke_blocking: true`:

1. The error description is passed as retry context
2. Ralph loop starts for the smoke fix (limited budget)
3. Max `smoke_fix_max_retries` (default: 3) attempts
4. If unsuccessful → change failed

| Parameter | Default | Description |
|-----------|---------|-------------|
| `smoke_command` | "" | Smoke test command |
| `smoke_timeout` | 120s | Smoke timeout |
| `smoke_blocking` | true | Blocking mode |
| `smoke_fix_token_budget` | 500K | Fix budget |
| `smoke_fix_max_turns` | 15 | Max fix iterations |
| `smoke_fix_max_retries` | 3 | Max retries |
| `smoke_dev_server_command` | "" | Command to start dev server |

### Dev Server Auto-Restart

If the health check fails before smoke tests, the orchestrator can auto-start a dev server:

```yaml
smoke_dev_server_command: "npx next dev --port 3002"
```

When configured, the orchestrator runs the command in the background, waits up to 60 seconds for the health check to pass, and proceeds with smoke tests. If the server fails to start, the change is marked `smoke_blocked`. The dev server process is automatically killed on orchestrator exit.

### Health Check

Optionally, an HTTP health check can be configured:

```yaml
smoke_health_check_url: "http://localhost:3000/api/health"
smoke_health_check_timeout: 30
```

Before running smoke tests, the system checks whether the application responds to HTTP. If the health check fails and `smoke_dev_server_command` is configured, a dev server restart is attempted automatically.

## E2E Gate

The most comprehensive test, examining the full application.

### Two Modes

| Mode | Description |
|------|-------------|
| `e2e_mode: per_change` | E2E runs before every change merge |
| `e2e_mode: phase_end` | E2E runs only at phase end, on the main branch |

The `phase_end` mode is more efficient for large projects, because E2E tests are often slow and produce more relevant results when run on the main branch.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `e2e_command` | "" | E2E test command |
| `e2e_timeout` | 120s | E2E timeout |
| `e2e_mode` | per_change | per_change/phase_end |

## Gate Order Summary

```
Ralph done
  → Test Gate (test_command, if configured)
    → Review Gate (review_before_merge, if active)
      → Verify Gate (scope check)
        → Smoke Gate (smoke_command, if configured)
          → E2E Gate (e2e_command, if configured)
            → ✓ Merge Queue
```

\begin{keypoint}
Every gate is optional. If there is no test\_command, the Test Gate is skipped. If review\_before\_merge is false, the Review Gate is skipped. With minimal configuration (no gates at all), the change goes directly to the merge queue after Ralph is done — but this is not recommended for production projects.
\end{keypoint}

## Merge Timeout

The entire merge pipeline (merge + post-merge build + smoke + fix cycles) is protected by a timeout. If elapsed time exceeds the limit, the merge is aborted at the next checkpoint and the change is marked `merge_timeout`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `merge_timeout` | 1800s (30min) | Max time for the entire merge pipeline |

Checkpoints are placed after the merge itself and before the smoke fix cycle. The timeout does not use a subprocess or `timeout` command — it uses checkpoint-based elapsed time checks to preserve flock and state file integrity.

## Hooks

Hooks can run between gates:

| Hook | When It Runs |
|------|-------------|
| `hook_post_verify` | After verify gate passes |
| `hook_pre_merge` | Before merge (blocking) |
| `hook_on_fail` | When a change enters failed status |
