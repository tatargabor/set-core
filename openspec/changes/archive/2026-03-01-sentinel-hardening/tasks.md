# Tasks: sentinel-hardening

## Group 1: Fix bash sentinel bugs

- [x] 1.1 Add `time_limit` to clean exit conditions in `bin/set-sentinel` (alongside `done` and `stopped`)
- [x] 1.2 Change default for `exit 0 + unknown state` to stop (not restart) — log the unexpected state
- [x] 1.3 Add `sentinel_log()` helper that writes to both stdout and orchestration.log with `[sentinel]` prefix
- [x] 1.4 Skip stale state modification when status is `checkpoint` (only reset `running` → `stopped`)

## Group 2: Sentinel skill command file

- [x] 2.1 Create `.claude/commands/wt/sentinel.md` with skill prompt containing: start orchestrator in background, poll loop bash script, decision tree, escalation rules, report format
- [x] 2.2 The poll loop script: bash `while true` that reads state.json every 15s, detects terminal states / checkpoint / stale / process exit, breaks with event type + details
- [x] 2.3 Decision tree in prompt: done→report, stopped→report, time_limit→summary, checkpoint→auto-approve or escalate, crash→diagnose, stale→investigate
- [x] 2.4 Checkpoint auto-approve logic: read `checkpoints[-1].reason`, if `periodic` → atomic write approved=true, else → report to user

## Group 3: Crash diagnosis prompt

- [x] 3.1 Add crash handling section to skill prompt: read last 50 log lines, classify as recoverable/fatal/unknown
- [x] 3.2 Known recoverable patterns list in prompt: jq errors, file lock timeouts, transient network errors
- [x] 3.3 Known fatal patterns list in prompt: missing files, auth failures, dependency errors
- [x] 3.4 Unknown error handling: restart once, if recurs → stop and report
- [x] 3.5 Rapid crash safety limit (5 consecutive <5min crashes) → give up regardless of diagnosis

## Group 4: Completion report

- [x] 4.1 Report template in skill prompt: status, active/wall duration, changes N/M, tokens, restarts, issues
- [x] 4.2 Agent reads state.json fields for report: `status`, `active_seconds`, `started_epoch`, `changes[]`, `prev_total_tokens`, `replan_cycle`

## Group 5: Documentation

- [x] 5.1 Create `docs/sentinel.md` — usage guide: what sentinel does, agent vs bash modes, how to start (`/wt:sentinel` from Claude session), arguments, what to expect, how it handles crashes/checkpoints/time-limits
- [x] 5.2 Add sentinel section to SKILL.md under worktree management skill (brief reference, points to docs)
