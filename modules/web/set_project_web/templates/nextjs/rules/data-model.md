---
paths:
  - "prisma/**"
  - "src/lib/prisma*"
---
# Data Model Conventions

## Prisma Schema
- Every model needs `createdAt` and `updatedAt` timestamps
- Use appropriate ID strategy for the project (auto-increment or cuid)
- Define explicit relations with clear naming

## Migrations
- Run `prisma migrate dev --name descriptive-name` to create migrations
- Migration names: `add_user_roles`, `create_order_table` (snake_case, descriptive)
- Review generated SQL before committing
- Never edit deployed migrations — create new ones to fix issues
- Never use `prisma db push` in production — always use migrations

## State Machines
- Use enum fields for states (e.g., `status OrderStatus`)
- Define valid transitions in code, not in schema

## Relations
- Use explicit relation names for self-referencing or ambiguous relations
- Cascade deletes only for true child entities (e.g., OrderItem → Order)
- Set `onDelete: SetNull` for optional references

## Seeding
- Use `prisma/seed.ts` with `tsx` runner
- Seed data should be idempotent (use `upsert` or check-before-insert)

## Worktree Setup

When working in a git worktree (parallel agent environment), `dev.db` is gitignored and must be initialized in each worktree:

```bash
# In every new worktree — run before tests or seed
npx prisma migrate deploy   # NOT migrate dev — deploy applies existing migrations non-interactively
npx prisma db seed          # seed data is not committed
```

**Why `migrate deploy` not `migrate dev`:** `migrate dev` is interactive and creates new migration files. In a worktree you want to apply existing migrations only.

## Prisma Version Pin

Pin `prisma@6` explicitly in `package.json`:
```json
"prisma": "6",
"@prisma/client": "6"
```

Prisma 7 introduced a breaking change: the `url` field in `datasource` blocks is no longer supported in the same form. Use v6 until explicitly migrating.
