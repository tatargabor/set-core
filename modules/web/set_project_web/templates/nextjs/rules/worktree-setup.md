---
paths:
  - "prisma/**"
  - "jest.config*"
  - "playwright.config*"
---
# Worktree Setup

Common setup steps required when working in a git worktree (parallel agent environment).

## Database Init

`dev.db` is gitignored. Every worktree needs its own database:

```bash
npx prisma migrate deploy   # apply existing migrations (non-interactive)
npx prisma db seed          # seed test data
```

Run these before executing tests or starting the dev server in a worktree.

## Port Conflicts

Multiple worktrees can't share the same port. Use the `PW_PORT` env var (set by the orchestrator per worktree) in `playwright.config.ts`:

```typescript
const PORT = process.env.PW_PORT ? parseInt(process.env.PW_PORT) : 3100;
```

Or pass `--port` explicitly: `pnpm dev --port 3101`

## pnpm Non-Interactive Mode

Add to `package.json` to prevent `pnpm approve-builds` from blocking in worktrees:

```json
{
  "pnpm": {
    "onlyBuiltDependencies": []
  }
}
```
