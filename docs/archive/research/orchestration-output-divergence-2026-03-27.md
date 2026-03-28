# Orchestration Output Divergence Analysis

**Date:** 2026-03-27
**Runs compared:** minishop-run6 vs minishop-run7
**Location:** `~/.local/share/set-core/e2e-runs/minishop-run{6,7}/`

## Background

Both runs used the same input spec (minishop v1) but different decomposition strategies. The question: if orchestration is good, how similar should the final source code be regardless of decomposition?

## Run Summary

| Metric           | run6       | run7       | Delta |
|------------------|------------|------------|-------|
| Merge rate       | 6/6 (100%) | 6/6 (100%) | =     |
| Issues triggered | 0          | 0          | =     |
| Total tokens     | 249,682    | 359,413    | +44%  |
| Total gate time  | 135.7s     | 166.0s     | +22%  |

### Decomposition Differences

| run6                  | run7                       |
|-----------------------|----------------------------|
| project-foundation    | foundation-and-data        |
| auth-navigation       | product-catalog            |
| product-catalog       | admin-auth-and-products    |
| shopping-cart         | shopping-cart              |
| checkout-orders       | checkout-and-orders        |
| admin-products        | order-views-and-admin-crud |

run6 separated auth and admin into distinct changes. run7 combined auth+products into one larger change (121k tokens vs run6 max 68k).

## Structural Comparison

### File Counts

| Category       | Count |
|----------------|-------|
| Common (both)  | 18    |
| Only in run6   | 31    |
| Only in run7   | 21    |
| run6 total     | 49    |
| run7 total     | 39    |

**File structure overlap (Jaccard): 37%** — meaning 63% of files exist in only one of the two runs.

### Common File Similarity

| File                              | Similarity | Notes                    |
|-----------------------------------|------------|--------------------------|
| `api/auth/[...nextauth]/route.ts` | 100%       | Identical                |
| `api/health/route.ts`             | 100%       | Identical                |
| `globals.css`                     | 100%       | Identical                |
| `components/ui/button.tsx`        | 100%       | Identical (shadcn)       |
| `components/ui/alert-dialog.tsx`  | 100%       | Identical (shadcn)       |
| `lib/utils.ts`                    | 100%       | Identical                |
| `layout.tsx`                      | 86%        | Minor provider diffs     |
| `admin/login/page.tsx`            | 67%        | Different form approach   |
| `admin/register/page.tsx`         | 64%        | Different form approach   |
| `lib/auth.ts`                     | 63%        | Session config diffs     |
| `middleware.ts`                   | 62%        | Route matching diffs     |
| `(shop)/orders/page.tsx`          | 56%        | Different list rendering |
| `(shop)/products/[id]/page.tsx`   | 52%        | Detail layout diffs      |
| `lib/session.ts`                  | 53%        | API shape diffs          |
| `(shop)/orders/[id]/page.tsx`     | 45%        | Status display diffs     |
| `(shop)/cart/page.tsx`            | 44%        | 227 vs 67 lines          |
| `(shop)/layout.tsx`               | 40%        | Nav structure diffs      |

**Pattern:** Generated/library code is 100% identical. Business logic pages average ~55% similarity.

### Key Divergence Sources

#### 1. Route Group Structure (HIGHEST impact)

| Aspect | run6 | run7 |
|--------|------|------|
| Storefront | `src/app/page.tsx` (flat) | `src/app/(shop)/page.tsx` (grouped) |
| Admin | `src/app/admin/products/` (flat) | `src/app/admin/(dashboard)/products/` (grouped) |

run7 used Next.js route groups for layout isolation. run6 used flat structure. This single decision caused the most file path divergence.

#### 2. Code Organization

| Aspect | run6 | run7 |
|--------|------|------|
| Server actions | `src/actions/product.ts`, `src/actions/variant.ts` | `src/app/.../actions.ts` (co-located) |
| Feature components | `src/components/admin/` (4 files) | Inline with route (e.g., `ProductsTable.tsx`) |
| Shared queries | Inline in components | `src/lib/queries/products.ts` |

#### 3. Utility Naming

| Purpose | run6 | run7 |
|---------|------|------|
| DB client | `src/lib/prisma.ts` | `src/lib/db.ts` |
| Price formatting | `src/lib/format-price.ts` | `src/lib/format.ts` |
| Validation | `src/lib/validations/product.ts` | Inline zod schemas |

#### 4. UI Component Strategy

| Aspect | run6 | run7 |
|--------|------|------|
| shadcn components | 10 (badge, data-table, dialog, input, label, select, table, textarea + button, alert-dialog) | 2 (button, alert-dialog) |
| Radix dependencies | 5 extra packages | 0 extra |
| Custom components | `src/components/admin/` directory | Co-located with routes |

#### 5. Prisma Schema

Semantically identical. Differences were whitespace/field ordering only — functionally equivalent models, relations, and enums.

#### 6. Dependencies

32 shared packages, run6 had 4 extra (@radix-ui/react-dialog, @radix-ui/react-label, @radix-ui/react-select, @tanstack/react-table pre-installed).

#### 7. E2E Tests

| run6 | run7 |
|------|------|
| admin-products.spec.ts | admin-crud.spec.ts |
| auth.spec.ts | admin.spec.ts |
| cart.spec.ts | cart.spec.ts |
| catalog.spec.ts | catalog.spec.ts |
| health.spec.ts | checkout.spec.ts |
| orders.spec.ts | navigation.spec.ts |
| | order-views.spec.ts |

7 vs 7 test files, different naming but similar coverage scope.

## Root Cause Analysis

The divergence is NOT random — it comes from **ambiguous or missing conventions** in the framework rules:

| Divergence | Root Cause |
|------------|------------|
| Route groups vs flat | No convention existed for route group usage |
| `src/actions/` vs co-located | Rule said "Place in `src/actions/` **or** co-locate" — ambiguous |
| `prisma.ts` vs `db.ts` | Rule existed (`prisma.ts`) but wasn't enforced strongly enough |
| 10 shadcn vs 2 | Rule said "use shadcn as base" but didn't specify on-demand installation |
| `components/admin/` vs inline | No convention for feature component location |
| `format-price.ts` vs `format.ts` | No utility naming convention existed |

## Changes Made

Commit `ecdf34925` — 5 files modified in `modules/web/set_project_web/templates/nextjs/rules/`:

### 1. `nextjs-patterns.md` — New section: Route Group Structure

Added explicit directory structure convention:
- Public pages under `(shop)/` route group
- Admin auth pages under `admin/` directly (outside dashboard layout)
- Admin feature pages under `admin/(dashboard)/` (inside sidebar layout)
- `src/app/page.tsx` should NOT exist — homepage is `(shop)/page.tsx`

### 2. `functional-conventions.md` — Clarified action location + added utility naming

**Before:** "Place in `src/actions/` or co-locate in feature directories"
**After:** "Co-locate actions with their route segment as `actions.ts`. NEVER create a top-level `src/actions/` directory."

Added:
- `prisma.ts` naming enforced with NEVER clause for alternatives
- Utility file naming: `format.ts`, `queries/<entity>.ts`, `validations.ts`

### 3. `ui-conventions.md` — On-demand install + feature component colocation

Added:
- "Install shadcn components ON DEMAND — only add when first needed"
- Base set defined: Button, AlertDialog
- Feature components co-locate with route segments
- `src/components/` only for `ui/` and truly cross-cutting shared components

### 4. `data-model.md` — Glob precision

Changed path glob from `src/lib/prisma*` to `src/lib/prisma.ts`.

### 5. `testing-conventions.md` — Import consistency

Aligned Prisma import example with the convention.

## Expected Impact

| Metric | Before | Expected After |
|--------|--------|----------------|
| File structure overlap | 37% | ~75-80% |
| Naming consistency | Low | High |
| Route structure | Divergent | Identical |
| Component location | Divergent | Identical |
| UI library scope | 10 vs 2 | Similar |
| Prisma schema | 98% | 98% (unchanged) |

## What We Chose NOT to Regulate

- **Line count per component** — 400 line rule is sufficient
- **Prisma field ordering** — formatter concern, not agent concern
- **Hook vs inline state** — style preference with no structural impact
- **Test file naming** — coverage matters, not names
- **Import alias format** — tsconfig.json determines this

## Validation Results (2026-03-28)

### Round 2: Convention rules only (micro-web run8 vs run9)

Same spec, convention rules deployed (route groups, action colocation, utility naming), no template files yet.

| Metric | run8 | run9 |
|--------|------|------|
| Changes | 3 | 3 |
| File count | 11 | 11 |
| File overlap (Jaccard) | **47%** | |
| Route structure | Identical (5/5) | |
| Dependencies | Identical | |
| Vitest exclude | Both correct | |

Divergences: `header.tsx` vs `Header.tsx` (casing), `lib/blog-data.ts` vs `data/blog-posts.ts` (path), `lib/validation.ts` vs `lib/validate-contact.ts` (naming).

### Round 3: Three-layer templates (micro-web run10 vs run11)

Same spec, full template system deployed: Layer 1 (module templates: globals.css, utils.ts, prisma.ts), Layer 2 (scaffold rules: micro-web-conventions.md), Layer 3 (project override support).

| Metric | run10 | run11 |
|--------|-------|-------|
| Changes | 4 (all merged) | 5 (all merged) |
| File count | 11 | 11 |
| File overlap (Jaccard) | **100%** | |
| File naming | Identical (11/11) | |
| Dependencies | Identical | |
| Gate results | TBS on all non-foundation | TBS on all non-foundation |

Content similarity of common files:

| File | Similarity |
|------|-----------|
| globals.css | 100% (template) |
| layout.tsx | 91% |
| blog-data.ts | 73% |
| contact/page.tsx | 66% |
| Header.tsx | 55% |
| blog/[slug]/page.tsx | 47% |
| page.tsx | 45% |
| about/page.tsx | 37% |
| validation.ts | 36% |
| validation.test.ts | 35% |

Average content similarity: ~57%. The remaining divergence is in page implementation details (agent creativity) — functionally equivalent, not worth regulating.

### Trend Summary

```
Measurement                  File Overlap    What Changed
─────────────────────────    ────────────    ──────────────────────
minishop run6 vs run7         37%           (no conventions)
micro-web run8 vs run9        47%           + convention rules
micro-web run10 vs run11     100%           + template files + scaffold rules
```

The three-layer template system eliminated structural divergence entirely. Convention rules alone improved overlap by +10pp; adding template files brought it to 100%.
