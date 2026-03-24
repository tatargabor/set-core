# Proposal: worktree-e2e-lifecycle

## Why

Parallel worktrees all use port 3000 for dev server and Playwright tests. When `max_parallel: 2+`, agents and verify gates collide — `ERR_SOCKET_NOT_CONNECTED`, blank screenshots, false e2e failures. Additionally, Prisma-based projects need `db push` + seed before e2e tests work, but no pre-gate phase exists.

Found in micro-web-run5: all 3 integration e2e gates failed with blank screenshots (port collision). The verify gate `execute_e2e_gate()` in `gates.py` also lacks port isolation — it just sets `PLAYWRIGHT_SCREENSHOT=on`.

## What Changes

- **Port isolation across full lifecycle**: deterministic port per worktree (hash-based), injected at bootstrap time into `.env` so agent, dev server, and gates all share the same port
- **Verify gate e2e port**: `execute_e2e_gate()` uses `profile.e2e_gate_env(port)` like integration gate already does
- **Pre-gate DB setup**: profile hook to run `prisma db push` + seed before e2e gate executes
- **Extensibility placeholder**: `e2e_pre_gate()` / `e2e_post_gate()` hooks in ABC for future Postgres/container support

## Capabilities

### New Capabilities
- `worktree-e2e-lifecycle`: Port isolation and DB lifecycle hooks for parallel worktree e2e testing

### Modified Capabilities
(none)

## Impact

- `lib/set_orch/profile_types.py` — new ABC methods: `worktree_port()`, `e2e_pre_gate()`, `e2e_post_gate()`
- `lib/set_orch/dispatcher.py` — `bootstrap_worktree()` writes PORT/PW_PORT to `.env`
- `modules/web/set_project_web/project_type.py` — implement port + Prisma lifecycle
- `modules/web/set_project_web/gates.py` — `execute_e2e_gate()` adds port env + calls pre/post hooks
