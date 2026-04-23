# Proposal: improve-investigator-robustness

## Why

The issue-investigation pipeline has three silent-failure modes that together cost a run multiple hours of blocked progress:

1. **Investigator `max_turns=20` is hardcoded and too tight.** A multi-file diagnosis, or a diagnosis that gets trapped re-reading a corrupted file, exhausts the budget before producing a usable plan. The investigation returns with `terminal_reason=max_turns`, confidence stays below the auto-fix threshold, and the issue silently stalls in DIAGNOSED.

2. **No watchdog on DIAGNOSED issues.** Once an issue lands in DIAGNOSED with low confidence (below `auto_fix_conditions.min_confidence`), the issue manager has no path forward: it does not transition to FIXING (confidence too low), does not transition to AWAITING_APPROVAL (no timeout configured for below-threshold diagnoses), and does not send a notification to the operator. The issue sits indefinitely.

3. **The investigator has no prompt-level guard against "corrupt-file loops".** When a source file contains duplicate blocks (merge artifact, bad auto-fix), the agent re-reads it across turns without progressing. Adding a single sentence to the prompt template could let it recognise the pattern and exit with a useful diagnosis instead of burning turns.

A smaller adjacent gap: **`set-recovery render_preview` does not warn about active fix-iss pipelines that reference changes outside the rollback scope.** An operator rolling back a subset of changes may leave fix-iss children mid-flight without realising. This is not a correctness bug, but it belongs in the same pass: it's polish around the investigation/rollback lifecycle.

## What Changes

- **NEW** `IssuesPolicyConfig.investigation.max_turns` (default 40) — plumbed from config through `investigator.spawn` into the `claude --max-turns <N>` CLI invocation.
- **NEW** `IssuesPolicyConfig.diagnosed_stall_hours` (default 2) — watchdog threshold for DIAGNOSED issues with no forward motion.
- **MODIFIED** `IssueManager.tick()` — new `_check_diagnosed_stalls()` step: for each DIAGNOSED issue older than `diagnosed_stall_hours`, fire a one-time notifier call (`on_stalled_diagnosis`) and record an audit entry. Optionally relax auto_fix to allow execution when `confidence >= 0.4 AND elapsed > 1h` (configurable low-confidence auto-fix escape hatch).
- **MODIFIED** `INVESTIGATION_PROMPT` — add a short section instructing the agent to recognise source-corruption patterns (duplicate imports, repeated code blocks) and emit a specific diagnosis ("source corruption, remove duplicates before retry") instead of looping.
- **MODIFIED** `recovery.render_preview` — add a WARNING section listing any ACTIVE issue (state in INVESTIGATING/DIAGNOSED/FIXING) whose `affected_change` is NOT in the rollback scope. The rollback still proceeds; the warning just surfaces collateral.

## Capabilities

### New Capabilities
- `investigation-robustness` — Configurable investigation budget, DIAGNOSED-stall detection, and agent-prompt hardening against corrupt-file loops.

### Modified Capabilities
- `issue-policy-engine` — `IssuesPolicyConfig` gains `investigation.max_turns` and `diagnosed_stall_hours`. Config loading (`from_dict`) threads the new keys through.
- `issue-state-machine` — `tick()` gains a `_check_diagnosed_stalls()` pass; DIAGNOSED issues over the threshold trigger one-time notifications.
- `investigation-runner` — `--max-turns` is sourced from config; the prompt template recognises corrupt-file patterns.
- `dispatch-recovery` — `render_preview` flags active issues outside the rollback scope.

## Impact

- Modified: `lib/set_orch/issues/policy.py` (InvestigationConfig + top-level config), `lib/set_orch/issues/investigator.py` (max_turns plumbing + prompt), `lib/set_orch/issues/manager.py` (tick watchdog), `lib/set_orch/recovery.py` (render_preview warning section).
- No state schema changes. No DB. No new external dependencies.
- Backwards-compatible: config defaults preserve prior behavior for `max_turns` (40 is strictly more generous than 20, so no existing successful investigation fails under the new default). `diagnosed_stall_hours` defaults to 2 — in projects where no DIAGNOSED issues exist, the watchdog is a no-op.
- The auto_fix relaxation (low-confidence escape) is opt-in via a new config key; default OFF to match current behavior.
