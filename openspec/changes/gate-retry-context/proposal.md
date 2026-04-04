# Change: gate-retry-context

## Why

When integration E2E gates fail and the orchestrator redispatches an agent to fix the failures, the agent receives only the test output and original scope. It does NOT receive:

1. **What it previously built** — no git log summary, no list of files created/modified
2. **What tests passed vs failed** — only the raw tail of test output (last 2000 chars), losing context about which tests actually work
3. **The agent's own completion summary** — the previous session's final output is lost

This forces the agent to "rediscover" its own work by reading files and git history, wasting 30-50% of the retry iteration on context recovery instead of fixing the actual failures.

Observed in craftbrew-run20: acceptance-tests agent wrote 7 journey test suites (22 tasks), but on gate retry got only failing test output + original scope with no mention of what it had already implemented.

## What Changes

### 1. Enrich retry context with git summary

In `_recover_integration_e2e_failed()`, before building `retry_ctx`, collect:
- `git log --oneline main..HEAD` — commits the agent made
- `git diff --stat main..HEAD` — files changed with line counts
- Last commit message (often contains the agent's completion summary)

Inject this as a "Previous Work Summary" section in the retry prompt.

### 2. Include structured test results

Parse the E2E test output to extract:
- Number passed / failed / flaky / skipped
- List of failing test names (already partially done, but truncated)

Format as a clear checklist in the retry prompt so the agent knows exactly what to fix.

### 3. Add role framing

Prefix retry context with: "You previously implemented this change successfully. The code is in your working tree. Integration E2E tests found failures that need fixing."

This eliminates the agent's need to figure out whether it needs to implement from scratch or fix existing code.

## Impact

- `lib/set_orch/engine.py` — `_recover_integration_e2e_failed()` builds richer retry context
- `lib/set_orch/dispatcher.py` — no changes needed (already passes `retry_context` through)
- No new dependencies, no config changes
