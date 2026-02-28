## ADDED Requirements

### Requirement: Max replan retry limit
The orchestrator SHALL limit consecutive replan failures to a configurable maximum (default: 3). WHEN the replan decomposition fails `MAX_REPLAN_RETRIES` times consecutively on the same cycle, the orchestrator SHALL set status to `"done"` with `"replan_exhausted": true` in state, log all failed change names as warnings, and exit the monitor loop.

#### Scenario: Replan decomposition fails repeatedly
- **WHEN** auto_replan_cycle returns rc=2 three consecutive times for the same replan cycle
- **THEN** the orchestrator SHALL set state status to `"done"`, add `"replan_exhausted": true` to state, log a warning listing all failed change names, and break from the monitor loop

#### Scenario: Replan succeeds after failures
- **WHEN** auto_replan_cycle returns rc=0 after 1-2 prior failures
- **THEN** the retry counter SHALL reset to 0 and the new changes SHALL be dispatched normally

### Requirement: Spec summary cache
The orchestrator SHALL cache LLM spec summarization results keyed by `brief_hash`. WHEN `auto_replan_cycle()` triggers `cmd_plan()` and the `brief_hash` matches the cached value, the orchestrator SHALL skip the LLM summarization call and use the cached summary text.

#### Scenario: Cache hit on replan retry
- **WHEN** auto_replan_cycle triggers cmd_plan and `.claude/spec-summary-cache.json` exists with matching `brief_hash`
- **THEN** the orchestrator SHALL skip the spec summarization LLM call and use the cached summary, saving ~50k tokens

#### Scenario: Cache miss on brief change
- **WHEN** the spec file has been modified (different brief_hash)
- **THEN** the orchestrator SHALL run fresh summarization and update the cache file

### Requirement: Failed change deduplication in replan
The orchestrator SHALL track previously-failed change names across replan cycles. WHEN the new plan contains ONLY changes that previously failed (no genuinely novel changes), the orchestrator SHALL treat this as "no new work" (rc=1) rather than dispatching the same failing changes again.

#### Scenario: Replan produces same failed changes
- **WHEN** all changes in the new plan match names of previously-failed changes AND no novel changes exist
- **THEN** auto_replan_cycle SHALL return 1 (no new work) and the orchestrator SHALL exit cleanly
