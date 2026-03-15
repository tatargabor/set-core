## Why

E2E run #13 analysis shows two recurring efficiency issues that waste agent time and degrade log quality:

1. **Missing post-install commands in web profile bootstrap** — Every worktree with Prisma fails its first build because `prisma generate` wasn't run after `pnpm install`. The agent spends ~2-5 minutes per change diagnosing and fixing this. Similarly, Playwright E2E tests fail until `playwright install chromium` is run manually. These are predictable post-install steps that the web profile should handle automatically.

2. **Heartbeat event noise** — `WATCHDOG_HEARTBEAT` events are emitted every poll cycle (~15s) into `events.jsonl`, comprising 71% of all events (75/106 in run #13). This makes log analysis difficult and inflates the events file unnecessarily. Heartbeats serve the sentinel's liveness detection but don't need to be persisted in the event log.

## What Changes

- Add post-install hooks to `wt-project-web` `bootstrap_worktree()`:
  - Run `prisma generate` if `prisma/schema.prisma` exists
  - Run `npx playwright install chromium` if `@playwright/test` is in devDependencies
- Throttle `WATCHDOG_HEARTBEAT` events in `engine.py` — emit to event bus at reduced frequency (e.g., every 5 minutes) instead of every poll cycle. Internal heartbeat logic unchanged.

## Capabilities

### New Capabilities
- `web-profile-bootstrap-hooks`: Post-install automation for web worktrees (prisma generate, playwright install)
- `heartbeat-event-throttle`: Reduce heartbeat noise in orchestration event log

### Modified Capabilities

## Impact

- `wt-project-web/wt_project_web/project_type.py` — `bootstrap_worktree()` method
- `wt-tools/lib/wt_orch/engine.py` — heartbeat emit logic in monitor loop
- Two repos affected: `wt-project-web` and `wt-tools`
