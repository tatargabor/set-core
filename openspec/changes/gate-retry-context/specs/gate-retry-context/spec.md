# Spec: gate-retry-context

## Capability

When an integration E2E gate fails and the orchestrator redispatches an agent, the agent receives a structured retry prompt that includes its previous work summary (commits, files changed), parsed test results (pass/fail counts, failing test names), and role framing so it can immediately focus on fixing failures instead of rediscovering its own code.

## Behavior

### Retry context builder

- `_build_gate_retry_context(change, wt_path, e2e_output)` returns a structured string
- Runs `git log --oneline main..HEAD` capped at 30 lines
- Runs `git diff --stat main..HEAD` capped at 50 lines
- Parses Playwright output for pass/fail/flaky/skipped counts
- Extracts failing test names from output
- Falls back to current behavior if git commands fail

### Integration with existing flow

- `_recover_integration_e2e_failed()` calls `_build_gate_retry_context()` instead of building retry_ctx inline
- No changes to `resume_change()` — it already passes retry_context through
- E2E output truncation (2000 chars) preserved in raw section

### Prompt structure

The retry prompt has these sections in order:
1. Role framing — "You previously implemented this, fix the failures"
2. Previous Work — commits and files changed
3. Test Results — structured pass/fail summary with failing test list
4. Test Output — raw output for error details
5. Original Scope — reference only
