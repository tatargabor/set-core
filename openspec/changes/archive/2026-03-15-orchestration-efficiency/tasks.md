# Tasks: orchestration-efficiency

## 1. Web profile bootstrap hooks (wt-project-web)

- [ ] 1.1 Add prisma generate to `bootstrap_worktree()` — after pnpm install, if `prisma/schema.prisma` exists, run `npx prisma generate` with 60s timeout, non-fatal on failure
- [ ] 1.2 Add playwright install to `bootstrap_worktree()` — if `@playwright/test` in devDependencies, run `npx playwright install chromium` with 120s timeout, non-fatal on failure
- [ ] 1.3 Add unit tests for bootstrap post-install hooks — test prisma detection, playwright detection, skip-when-absent, failure-is-non-fatal

## 2. Heartbeat event throttle (wt-tools)

- [ ] 2.1 Throttle `WATCHDOG_HEARTBEAT` emit in `engine.py` — emit only every 20th poll cycle (`poll_count % 20 == 0`), keep internal heartbeat logic unchanged
- [ ] 2.2 Add unit test for heartbeat throttle — verify emit frequency reduced, verify first heartbeat is immediate
