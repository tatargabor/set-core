# Proposal: e2e-env-bootstrap

## Why

E2E tests fail in worktrees because `.env` (with DATABASE_URL) is gitignored and not bootstrapped. Agents create `.env` during implementation, but it's lost on worktree recreation (sentinel reset) and missing in fresh dispatches. The integration gate now loads `.env` from worktree, but the file itself needs to exist.

## What Changes

- **ENHANCE**: `WebProjectType.bootstrap_worktree()` — if `prisma/schema.prisma` exists and no `.env`, generate `DATABASE_URL="file:./dev.db"`
- **ENHANCE**: `config.yaml` support for `env_vars` section — key-value pairs written to `.env` in every worktree at bootstrap time
- **NEW**: Test coverage for env bootstrap in web module

## Capabilities

### Modified Capabilities
- `web-bootstrap`: Auto-generate .env for Prisma projects
- `dispatcher-env`: Config-driven env var injection

## Impact

- **Modified files**: `modules/web/set_project_web/project_type.py`, `lib/set_orch/dispatcher.py`
- **Risk**: Low — only creates `.env` if missing, never overwrites
- **Dependencies**: None
