## Context

Three engine inefficiencies observed in the set-designer v2 run:
1. E2E gate retry context says "suite crashed" without the webServer log that explains why
2. Agents that say "done" without committing anything still consume retry budget
3. fix-iss agents spend ~1 hour creating openspec artifacts before touching code

All three have precise code locations and bounded fixes.

## Goals / Non-Goals

**Goals:**
- Agent sees webServer stderr in retry context on first retry
- No-commit retries don't decrement retry budget
- fix-iss agents skip openspec ceremony and go straight to code

**Non-Goals:**
- Integration smoke baseline comparison (separate change)
- Flaky test detection
- Retry context escalation (progressive diagnostics per retry)

## Decisions

### D1: Extract webServer log section from combined e2e output

The E2E gate already captures `stdout + stderr` in `e2e_output` (`gates.py:1388`). Lines prefixed with `[WebServer]` are the webServer's output. When the gate fails without parseable failures (line 1636) or on timeout (line 1494), extract `[WebServer]` lines from the output and append them to the retry context.

**Why not capture webServer stderr separately:** Playwright interleaves `[WebServer]` lines into combined output. Separating at the process level would require modifying `run_command()` — high blast radius. Regex extraction from the combined output is safe and sufficient.

### D2: No-commit retry guard using `_has_commits_since_gate`

`_has_commits_since_gate(wt_path, last_gate_commit)` already exists in `engine.py:1470`. The verifier's `handle_change_done()` should call this before incrementing `verify_retry_count`. If HEAD == last_gate_commit, the agent didn't commit anything new — log a warning and re-dispatch without consuming retry budget.

**Why not skip the re-dispatch entirely:** The agent might have a different approach on the next try even without new commits (e.g., reading different files, using a different strategy). We just don't want to penalize it with a retry count increment.

## Risks / Trade-offs

- **[Risk] webServer log extraction regex might miss non-standard prefixes** → Mitigation: fall back to last 50 lines of raw output if no `[WebServer]` lines found
- **[Risk] No-commit guard might mask a real "agent committed but force-pushed" scenario** → Mitigation: `_has_commits_since_gate` checks `git log last_gate_commit..HEAD` which handles force-push correctly (returns True if HEAD changed)

## Open Questions

None.
