# Nano — Rapid E2E Validation Scaffold

> The smallest possible Next.js + Prisma + shadcn/ui + Playwright project that still exercises the full set-core gate pipeline. Used for quick reproducibility testing after core changes — target full runtime under 10 minutes.

## Purpose

This scaffold is NOT a realistic application. It is a **test surface** for set-core itself: every gate (build, test, e2e, lint, scope_check, test_files, e2e_coverage, spec_verify, rules, review, integration smoke, integration own-tests, merge pipeline) must fire at least once across the two changes, and the full run should complete in 5-10 minutes on a dev machine.

When you change set-core and want to validate it quickly without spinning up minishop or craftbrew (both ~1-2 hours), run nano first.

## Non-goals

- No design tokens, no figma, no design-brief, no design.md per change. UI uses raw shadcn defaults.
- No authentication, no accounts, no scoping.
- No API routes (Server Actions only).
- No multi-user concerns.
- No i18n, no SEO, no meta tags beyond defaults.
- No analytics, no telemetry.
- Do NOT add features beyond the 2 changes below. Simplicity IS the point.

## Stack

- Next.js 14+ (App Router, Server Actions)
- Prisma + SQLite (`file:./dev.db`)
- shadcn/ui — ONLY `Button` and `Input` components. Nothing else.
- Playwright E2E (one worker, shared dev.db across specs)
- vitest unit (accept `passWithNoTests` — no unit tests required)

## Data model

Single table — `Item`:

```prisma
model Item {
  id        Int      @id @default(autoincrement())
  text      String
  createdAt DateTime @default(now())
}
```

Seed with 2 items on migration: `"hello"` and `"world"`.

## Pages

Single page only — `GET /`:
- Lists all `Item` rows ordered by `createdAt DESC`
- Each item renders as a `<li>` with the `text` field
- Empty state: `<p>No items yet.</p>` when the list is empty
- Header `<h1>Nano</h1>`

No other routes. No `/about`, no detail views, no admin panel.

## Features (implementation changes)

### Change A: `infra` — Prisma schema, layout, home page, empty state

- Create `prisma/schema.prisma` with the `Item` model above + SQLite datasource
- Create `prisma/seed.ts` that inserts `"hello"` and `"world"` on first run
- Add `prisma.seed` entry to `package.json`
- Update `scripts.build` to `prisma generate && prisma db push --accept-data-loss && next build`
- Install shadcn `button` and `input` components (via `npx shadcn@latest add button input`)
- Create `src/app/layout.tsx` — root layout with `<html>`, `<body>`, Tailwind globals, and a header `<h1>Nano</h1>` above `{children}`
- Create `src/app/page.tsx` — server component that reads all items via Prisma and renders them, empty state if none
- E2E test: `tests/e2e/infra.spec.ts`
  - `REQ-INFRA-001:AC-1 — GET / returns 200 with at least 2 seeded items @SMOKE` — tag `@smoke`, uses `page.goto('/', { waitUntil: 'networkidle' })`, counts rows via `.count() >= 2` (NEVER exact count)
  - `REQ-INFRA-001:AC-2 — Empty state message shown when no items` — deletes all items via Prisma in `test.beforeAll`, asserts `<p>No items yet.</p>` is visible, restores seed in `test.afterAll`
- Update `START.md` with `pnpm install && pnpm exec prisma db push && pnpm exec prisma db seed && pnpm dev` commands

**REQ-INFRA-001:AC-1** — Home page renders seeded items
**REQ-INFRA-001:AC-2** — Empty state is shown when no items exist

### Change B: `add-item` — Server Action + form + list update

- Create `src/app/actions.ts` — `async function addItem(formData: FormData)` Server Action:
  - Extract `text` field (String)
  - Validate: trim, reject empty string, reject length > 255 chars, return `{ success: false, error }` on failure
  - On success: `prisma.item.create({ data: { text } })`, `revalidatePath('/')`, return `{ success: true }`
- Create `src/app/add-item-form.tsx` — client component `'use client'`, uses shadcn `<Input>` + `<Button>` components, binds to the `addItem` Server Action
- Update `src/app/page.tsx` to render the form above the item list
- E2E test: `tests/e2e/add-item.spec.ts` — uses `waitUntil: 'networkidle'` on ALL page.goto:
  - `REQ-ADD-001:AC-1 — Submitting 'nano-test-seed' creates a new item visible in the list @SMOKE` — tag `@smoke`, types `"nano-test-seed"` into the input, clicks "Add", asserts a row containing `"nano-test-seed"` appears (uses `.filter({ hasText: 'nano-test-seed' })` to avoid counting seed rows)
  - `REQ-ADD-001:AC-2 — Empty input does not create an item` — submits with blank input, asserts no new row is added
  - `REQ-ADD-001:AC-3 — Server Action is used (no API route)` — checks that the form uses the Server Action pattern (action={addItem}, not fetch('/api/...'))

**REQ-ADD-001:AC-1** — Form creates a new item visible in the list
**REQ-ADD-001:AC-2** — Blank/whitespace input is rejected
**REQ-ADD-001:AC-3** — Implementation uses Server Action, not API route

## Testing conventions

These are the bare minimum conventions the agents must follow — they prevent every known silent-pass and cross-spec pollution issue:

- **ALWAYS use `await page.goto(url, { waitUntil: 'networkidle' })`.** Never use bare `page.goto(url)`.
- **NEVER assert exact counts on rows.** The dev.db is shared across specs in one Playwright worker. Use `.count() >= N` or `.filter({ hasText: 'known-name' })`.
- **Server actions accepting text input MUST validate max length** (255 chars for `Item.text`).
- **Use unique test row names** (e.g., `"nano-test-seed"`, `"nano-test-B"`) so `.filter()` queries are precise and specs never collide.
- **Use `getByLabel("Label", { exact: true })`** when the label text could prefix-match another label.
- **DO NOT alter the test:e2e npm script.** If the orchestrator's smoke invocation fails, that is a set-core framework bug; do NOT work around it by modifying `package.json`.
- **DO NOT create additional routes, pages, or features.** The scope is intentionally narrow. A change that adds a `/about` page or an admin route fails review.

## Done definition

1. Both changes merged through integration gates with zero silent-pass incidents
2. All 5 E2E specs pass in both worktree and integration stages
3. The full run completes in under 12 minutes (stretch: 8 minutes)
4. Final `/` renders `"Nano"` header + form + list containing at least the 2 seeded items plus any added during testing
