# Design: e2e-env-bootstrap

## Context

Prisma-based Next.js projects require `DATABASE_URL` in `.env` for the Prisma client to work. Agents create this during implementation, but the file is gitignored and lost on worktree recreation. The `bootstrap_worktree()` already copies `.env` from main → worktree, but it only works if main has one (which it doesn't for gitignored files).

## Decisions

### D1: WebProjectType generates .env if Prisma detected
In `bootstrap_worktree()`, check for `prisma/schema.prisma`. If exists and no `.env`:
- Parse schema for `env("DATABASE_URL")`
- Generate `.env` with `DATABASE_URL="file:./dev.db"` (SQLite default)
- For non-SQLite providers, log a warning but don't generate

### D2: Config-driven env_vars in orchestration config
Support `env_vars` section in `config.yaml`:
```yaml
env_vars:
  DATABASE_URL: "file:./dev.db"
  NEXTAUTH_SECRET: "dev-secret-do-not-use-in-production"
```
These get written to `.env` in every worktree at bootstrap time. Profile-generated values are overridden by config values.

### D3: Never overwrite existing .env
If `.env` already exists in worktree, don't touch it. The agent may have customized it.

## Files

| File | Change |
|------|--------|
| `modules/web/set_project_web/project_type.py` | `bootstrap_worktree()`: Prisma .env generation |
| `lib/set_orch/dispatcher.py` | `bootstrap_worktree()`: config.yaml env_vars → .env |
| `tests/unit/test_dispatcher.py` | env_vars bootstrap tests |
| `tests/modules/test_web_project_type.py` | Prisma .env generation tests |
