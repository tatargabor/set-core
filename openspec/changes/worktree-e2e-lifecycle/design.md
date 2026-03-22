# Design: worktree-e2e-lifecycle

## Decision 1: Deterministic port per worktree

**Choice**: `hash(change_name) % 1000 + 3100` — port range 3100-4099, deterministic per change name.

**Rationale**: Same port every time for the same change → agent can restart dev server without port drift. Range starts at 3100 to avoid 3000 (default Next.js) and common dev ports.

**Where it's set**: `bootstrap_worktree()` writes `PORT=<N>` and `PW_PORT=<N>` to `.env` in the worktree. The agent, `next dev`, and Playwright all read from `.env` or env vars.

**Integration gate**: Uses separate range (4000-4999, already implemented) since the agent worktree may still have lingering processes.

## Decision 2: Profile-driven port mapping

**Choice**: `worktree_port(change_name) → int` on `ProjectType` ABC. Web module implements the hash. Core only calls it during bootstrap.

**Rationale**: Different project types may have different port needs (e.g., mobile emulator ports, API gateway ports). Core shouldn't know the port scheme.

**Default**: ABC returns `0` (no port injection). Only profiles that override get port isolation.

## Decision 3: Pre/post gate hooks

**Choice**: Add `e2e_pre_gate(wt_path, env)` and `e2e_post_gate(wt_path)` to `ProjectType` ABC. Called by the e2e gate runner around test execution.

```
execute_e2e_gate():
  env = profile.e2e_gate_env(port)
  profile.e2e_pre_gate(wt_path, env)    ← NEW: DB setup
  run_command(e2e_cmd, env=env)
  profile.e2e_post_gate(wt_path)        ← NEW: cleanup
```

**Web implementation of `e2e_pre_gate()`**:
1. If `prisma/schema.prisma` exists → `npx prisma db push --skip-generate`
2. If `prisma/seed.ts` or `prisma/seed.js` exists → `npx prisma db seed`
3. Both use the worktree's `.env` (which has the correct DATABASE_URL)

**Web implementation of `e2e_post_gate()`**: No-op for now. Playwright `webServer` handles server lifecycle. Future: kill orphan dev servers if needed.

## Decision 4: .env PORT injection during bootstrap

**Choice**: `bootstrap_worktree()` calls `profile.worktree_port(change_name)` and if > 0, appends `PORT=<N>` and `PW_PORT=<N>` to the worktree's `.env`.

**Important**: Appends, doesn't overwrite — `.env` may already have `DATABASE_URL` and other vars from the main project copy.

**Idempotent**: If `PORT=` already in `.env`, skip (re-bootstrap after sync shouldn't change port).

## Decision 5: Postgres placeholder

**Choice**: Leave `e2e_pre_gate()` extensible. The web module checks for `prisma/schema.prisma` — if using Postgres, `DATABASE_URL` in `.env` should point to a per-worktree DB. The template's `config.yaml` has `DATABASE_URL: "file:./dev.db"` (SQLite default). For Postgres, user overrides to `postgres://.../<project>_${CHANGE_NAME}`.

**Future**: A `db_isolation_strategy` directive in `config.yaml` could auto-create per-worktree DBs. Not in scope now.

## Port Allocation Map

```
Range       Used By                    Set Where
─────────── ────────────────────────── ──────────────────
3000        Default (no isolation)     next.config.js default
3100-4099   Agent worktrees            bootstrap_worktree → .env
4000-4999   Integration gate           merger.py (existing)
5000-5999   Phase-end e2e              verifier.py (existing)
```
