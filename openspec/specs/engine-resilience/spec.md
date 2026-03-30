# Spec: Engine Resilience

## Status: new

## Requirements

### REQ-ENGINE-SIDECAR-MERGE: Merger must handle i18n sidecar files during archive
- When archiving a change that added i18n sidecar files (e.g., `messages/hu.feature_name.json`), the merger's archive step should either:
  - (a) Merge sidecar content into base message files (`messages/hu.json`) and delete sidecars, OR
  - (b) Ensure `i18n/request.ts` imports are wrapped in try/catch before deleting sidecars
- Currently: archive deletes sidecar files but leaves bare imports → app crashes → all E2E tests fail
- This was the root cause of ISS-001 and ISS-002 in production runs

### REQ-ENGINE-REDISPATCH-BRANCH: Redispatch must preserve prior committed work
- When the watchdog redispatches a stalled/dead agent, it MUST branch the new worktree from the change's existing branch (if it has commits ahead of main), not from main
- Currently: redispatch always creates fresh branch from main → loses all committed artifacts from the dead agent's worktree
- This was the root cause of ISS-003 and ISS-004 — same artifacts recreated 3 times, wasting ~90 minutes
- Safety: if the existing branch has merge conflicts with main, fall back to branching from main

### REQ-ENGINE-ISSUE-TIMEOUT: Issue pipeline ownership must have a timeout
- When the issue investigation pipeline owns a stalled change, stall recovery is blocked indefinitely
- Add configurable timeout (default: 30 minutes) — if issue pipeline hasn't resolved the change within the timeout, release ownership and allow normal stall recovery (redispatch)
- Log a warning when issue ownership approaches timeout
- This was the root cause of ISS-005 — manual intervention was required to unblock recovery
