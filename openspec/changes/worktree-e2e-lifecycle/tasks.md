# Tasks: worktree-e2e-lifecycle

## 1. Core ABC methods
- [x] 1.1 Add `worktree_port(change_name: str) -> int` to `ProjectType` in `profile_types.py` — default returns 0
- [x] 1.2 Add `e2e_pre_gate(wt_path: str, env: dict) -> bool` to `ProjectType` — default returns True (no-op)
- [x] 1.3 Add `e2e_post_gate(wt_path: str) -> None` to `ProjectType` — default no-op

## 2. Bootstrap port injection
- [x] 2.1 In `dispatcher.py` `bootstrap_worktree()`: call `profile.worktree_port(change_name)` and if > 0, append `PORT=<N>` and `PW_PORT=<N>` to worktree `.env`
- [x] 2.2 Make it idempotent — skip if `PORT=` already in `.env`
- [x] 2.3 Pass `change_name` through to `bootstrap_worktree()` (currently not passed)

## 3. Verify gate e2e port isolation
- [x] 3.1 In `gates.py` `execute_e2e_gate()`: load profile, call `e2e_gate_env(port)` to build env dict (replace hardcoded `PLAYWRIGHT_SCREENSHOT` only)
- [x] 3.2 Read port from worktree `.env` if available, or compute from `worktree_port(change_name)`
- [x] 3.3 Call `profile.e2e_pre_gate(wt_path, env)` before running e2e command
- [x] 3.4 Call `profile.e2e_post_gate(wt_path)` after e2e command (in finally block)

## 4. Web module implementation
- [x] 4.1 `worktree_port(change_name)` — `hash(change_name) % 1000 + 3100`
- [x] 4.2 `e2e_pre_gate(wt_path, env)` — prisma db push if schema.prisma exists + seed if seed file exists
- [x] 4.3 `e2e_post_gate(wt_path)` — no-op for now (comment: future cleanup)
- [x] 4.4 Ensure `e2e_gate_env(port)` also adds `PLAYWRIGHT_SCREENSHOT=on` (move from gates.py)

## 5. Tests
- [x] 5.1 Unit test: `worktree_port()` returns deterministic port in range 3100-4099
- [x] 5.2 Unit test: bootstrap writes PORT/PW_PORT to .env, idempotent on re-run
- [x] 5.3 Unit test: `e2e_pre_gate()` calls prisma when schema exists, no-op when absent

## Acceptance Criteria
- [x] Two parallel worktrees get different ports
- [x] Verify gate e2e uses worktree-specific port (no port 3000)
- [x] Prisma db push runs before e2e when schema.prisma exists
- [x] Non-web projects unaffected (ABC defaults to no-op)
