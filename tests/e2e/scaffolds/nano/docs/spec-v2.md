# Nano v2 — Delete Item Lineage Validation

> Increment on top of `spec.md` (v1).  Used to validate the lineage handoff:
> sentinel finishes v1, stops, restarts on `docs/spec-v2.md`.  v2 archives
> v1's plan/digest under their slugs, then runs ONE small change that touches
> the existing data model.  Total v2 runtime target: under 5 minutes.

## Lineage flow this spec exercises

1. Sentinel runs `docs/spec.md` (v1) → both `infra` and `add-item` merge.
2. Operator stops sentinel.  Live state has `spec_lineage_id = docs/spec.md`.
3. Operator starts sentinel with `--spec docs/spec-v2.md` (v2):
   - Plan/digest are rotated to the v1 slug
   - Live state's `spec_lineage_id` flips to `docs/spec-v2.md`
   - State-archive rows from v1 stay tagged with `docs/spec.md`
4. v2's single change merges.  Sidebar must now list both lineages; clicking
   v1 must reveal v1's two archived changes; v2 stays live.

The lineage Playwright suite (`web/tests/e2e/lineage.spec.ts`) verifies the
UI contract once the run finishes.

## Stack

Identical to v1 — Next.js 14 App Router, Prisma + SQLite, shadcn `Button`.
No new dependencies.

## Data model

NO migration.  v2 reuses the existing `Item` table verbatim.  Deletion is a
hard delete (no soft-delete column) — the goal is to keep the diff small,
not to model a real product.

## Pages

Same single page (`GET /`).  Each `<li>` row gains a "Delete" button to the
right of the text.

## Features (implementation changes)

### Change C: `delete-item` — Server Action + per-row delete button

- Add `async function deleteItem(id: number)` to `src/app/actions.ts`:
  - Coerce `id` to integer; reject `NaN` or non-positive ids with
    `{ success: false, error: 'invalid id' }`
  - On success: `await prisma.item.delete({ where: { id } })`,
    `revalidatePath('/')`, return `{ success: true }`
  - Catch `P2025` (record not found) and return
    `{ success: false, error: 'not found' }`
- Update `src/app/page.tsx` so each `<li>` renders text + a small `<form>`
  bound to `deleteItem`, with a hidden `<input type="hidden" name="id" />`
  carrying the row id and a shadcn `<Button variant="destructive" size="sm">Delete</Button>`.
  Wrap the form in `'use server'` if needed for inline binding.
- E2E test: `tests/e2e/delete-item.spec.ts` — uses
  `waitUntil: 'networkidle'` on all `page.goto`:
  - `REQ-DEL-001:AC-1 — Clicking Delete on a row removes that row from the list @SMOKE`
    — tag `@smoke`, seeds a row with text `"nano-del-target"`, asserts it is
    visible, clicks the Delete button on that row, asserts the row disappears
    via `.filter({ hasText: 'nano-del-target' })`'s `.count()` going to 0.
    Cleanup: ensure no `"nano-del-target"` rows remain in `test.afterEach`.
  - `REQ-DEL-001:AC-2 — Deleting an already-removed id is a no-op (no 500)` —
    seeds a row, captures its id via Prisma, deletes it twice through the
    Server Action, asserts the second call resolves with `success: false`
    AND the page still renders 200.

**REQ-DEL-001:AC-1** — Delete button removes the row
**REQ-DEL-001:AC-2** — Deleting a missing id returns `success: false`, no crash

## Testing conventions

Same as v1 (`docs/spec.md`):

- ALWAYS `await page.goto(url, { waitUntil: 'networkidle' })`
- NEVER assert exact row counts on the shared dev.db — use `.filter({ hasText: ... })`
- Use unique test row names (`"nano-del-target"`, NOT `"hello"`) so we
  cannot accidentally delete v1's seed data
- DO NOT add new pages, routes, or columns — the diff for v2 must stay
  surgical so the lineage flow is the dominant signal

## Done definition

1. The single `delete-item` change merges through integration gates with
   zero silent-pass incidents
2. `/api/<project>/lineages` lists BOTH `docs/spec.md` and `docs/spec-v2.md`
3. `/api/<project>/state?lineage=docs/spec.md` returns v1's `infra` +
   `add-item` archived changes; `?lineage=docs/spec-v2.md` returns the live
   `delete-item` change
4. The lineage Playwright suite passes 8/8 against this run as
   `E2E_PROJECT=<this-run-name>`
5. Total v2 runtime under 5 minutes
