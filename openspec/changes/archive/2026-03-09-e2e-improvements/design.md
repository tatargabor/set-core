## Context

The E2E minishop scaffold tests set-core orchestration end-to-end. Currently it's a simple Express+SQLite API with 4 changes. We're upgrading to Next.js + Prisma + shadcn/ui to test a realistic modern web stack — the same stack `set-project-web` targets. This will expose bugs in how agents handle complex frameworks, cross-cutting changes, and merge conflicts.

## Goals / Non-Goals

**Goals:**
- Fix token counting to be per-worktree accurate
- Rewrite E2E scaffold as Next.js App Router + Prisma (SQLite) + shadcn/ui + Tailwind
- Design a challenging feature roadmap (6 changes with dependencies, cross-cutting auth, shared components)
- Add Playwright E2E browser tests to the scaffold
- Generate a post-run report with screenshots, timeline, and stats
- Everything runs locally (localhost:3000), no deploy needed

**Non-Goals:**
- Deployment (Docker, Vercel) — local only
- Payment processing — orders are the end of the flow
- Real-time features (WebSocket, SSE)
- External services (email, SMS, S3)

## Decisions

### D1: Token Scoping — project-dir filter

`UsageCalculator.iter_jsonl_files()` currently walks ALL subdirs under `~/.claude/projects/`. Add an optional `project_dir` parameter that filters to a single project directory.

In `get_current_tokens()`, derive the project dir name from `$PWD` using Claude's observed encoding: replace `/` with `-`, strip leading `-`. Pass it to `wt-usage --project-dir <name>`. Note: this encoding is reverse-engineered from observed behavior and may not cover all edge cases (spaces, Unicode). The fallback to unfiltered scanning is the primary safety net.

Backward compatible — without the flag, behavior is unchanged. Also change `iter_jsonl_files()` to use recursive glob (`rglob('*.jsonl')`) to include subagent session subdirectories.

### D2: Scaffold Stack — Next.js App Router

**Stack:**
- **Framework:** Next.js 14+ App Router (`app/` directory)
- **Database:** Prisma ORM + SQLite (file-based, zero config)
- **UI:** shadcn/ui components (Radix primitives + Tailwind)
- **CSS:** Tailwind CSS
- **Auth:** NextAuth.js v5 (Auth.js) — App Router native, `auth()` for session access, Credentials provider, JWT session strategy, bcryptjs passwords
- **Package manager:** pnpm
- **Testing:** Jest + React Testing Library (unit), Playwright (E2E)

**Why this stack:** Matches `set-project-web` conventions exactly. More complex than Express — agents must handle:
- App Router file conventions (`page.tsx`, `layout.tsx`, `loading.tsx`)
- Server Components vs Client Components (`"use client"`)
- Server Actions for mutations
- Prisma schema + migrations
- shadcn/ui component library integration
- Tailwind utility classes
- TypeScript throughout

### D3: Feature Roadmap — 6 Changes

The v1-minishop spec defines these changes in dependency order:

1. **`products-page`** — Server-rendered product catalog page with shadcn Card grid. Prisma query in Server Component. Seed data in Prisma seed script. Tests: product listing renders, individual product shows correct data.

2. **`cart-feature`** *(depends: products-page)* — Server-side cart persisted in Prisma `CartItem` table. Anonymous sessions via UUID cookie. "Add to Cart" via Server Action on product cards, cart page with quantity controls, running total. shadcn Sheet/Dialog for cart preview. Tests: add to cart, remove, quantity update.

3. **`orders-checkout`** *(depends: cart-feature, products-page)* — Checkout flow: cart → order creation via Server Action (transactional: create order, order items, decrement stock, clear cart). Orders page showing history. Tests: place order, stock decremented, order in history.

4. **`admin-auth`** *(depends: products-page)* — NextAuth.js Credentials provider. Login/register pages. Protected admin routes via middleware. Admin layout with sidebar nav. Tests: register, login, access control.

5. **`admin-products`** *(depends: admin-auth, products-page)* — CRUD admin panel for products using shadcn DataTable. Server Actions for create/update/delete. Form validation with zod + react-hook-form. Image URL field (no upload). Tests: add product appears in catalog, edit updates, delete removes.

6. **`playwright-e2e`** *(depends: all above)* — Playwright test suite covering full user journey: browse → cart → order → admin login → manage products. Screenshot capture for E2E report. Responsive viewport tests (mobile + desktop).

**Why 6 changes:** Tests `max_parallel: 2` with deeper dependency chains. Changes 1-2 and 1-4 can parallelize (products + admin-auth). The cross-cutting nature of auth (change 4 modifies middleware that affects all routes) tests merge conflict handling. The Playwright change depends on everything, testing final integration.

### D4: Scaffold = Spec Only

The scaffold is a single file: `docs/v1-minishop.md`. This is the sole input to the E2E test. Agents build everything from this spec — package.json, Prisma schema, seed data, all app code, all tests.

```
tests/e2e/scaffold/
└── docs/
    └── v1-minishop.md    ← THE ONLY INPUT
```

**Why no pre-built files:**
- `package.json` — agent generates from spec. Version non-determinism is acceptable; the test validates orchestration, not pinned deps.
- `prisma/` — schema and seed described in spec text. Agent creates the files.
- `.env` — not needed. SQLite uses hardcoded `file:./dev.db` in schema. NextAuth secret has dev default in code.
- Config files (tsconfig, tailwind, next.config, etc.) — deployed by `set-project init --project-type web --template nextjs`.
- CLAUDE.md and rules — deployed by `set-project init`.
- shadcn components — agents add via `pnpm dlx shadcn@latest add`.

**E2E run.sh flow:**
1. Create empty directory
2. `cp scaffold/docs/v1-minishop.md <project>/docs/`
3. `cd <project> && git init`
4. `set-project init --project-type web --template nextjs` → deploys configs, rules, CLAUDE.md
5. `set-orchestrate` → planner reads `docs/v1-minishop.md`, creates changes, agents build everything

**What agents create during orchestration (everything):**
- `package.json` with all dependencies
- `prisma/schema.prisma` + `prisma/seed.ts`
- `src/app/layout.tsx`, `page.tsx`, all route pages
- `src/components/ui/*.tsx` — shadcn components
- `src/actions/*.ts` — server actions
- `src/lib/prisma.ts`, `src/lib/utils.ts`
- `middleware.ts` — auth middleware
- `jest.config.ts`, test files
- `playwright.config.ts`, E2E test files

### D5: Post-Run E2E Report

`bin/wt-e2e-report` reads `orchestration-state.json` and generates:
- Markdown report at `e2e-report.md`
- Per-change table: name, status, tokens, duration, test count
- Timeline with state transitions
- Playwright screenshots embedded/linked from `e2e-screenshots/`

After orchestration completes:
1. Start the app (`pnpm dev &`, wait for server)
2. Run Playwright screenshot script (headless Chromium)
3. Kill server
4. Generate report

### D6: Conventions via set-project-web

No scaffold CLAUDE.md — conventions are deployed by `set-project init --project-type web --template nextjs`. The nextjs template provides:
- Config files: `tsconfig.json`, `tailwind.config.ts`, `next.config.js`, `postcss.config.mjs`, `components.json`
- Rules: `ui-conventions.md`, `functional-conventions.md`, `auth-conventions.md`, `data-model.md`
- Project knowledge YAML

Project-specific conventions (currency format, seed data, SQLite hardcode, dev auth secret) live in the spec (`v1-minishop.md`), not in CLAUDE.md.

## Risks / Trade-offs

- **Agent version non-determinism** — without pinned `package.json`, agents choose dependency versions. Acceptable: the test validates orchestration workflow, not specific versions. If this causes flaky failures, we can add version hints to the spec.
- **Playwright download** — ~130MB for Chromium. Only needed for change 6 and report.
- **More complex = more failure modes** — that's the point. We want to find set-core bugs with a realistic workload.
- **Full agent autonomy** — agents must create everything from spec (package.json, prisma schema, all code). This is a harder test but more realistic. If init fails, the entire E2E fails — but that's a valid signal that specs need improvement.
- **set-project-web dependency** — the E2E now depends on the `set-project-web` plugin being installed and working. This is intentional: it validates both the plugin and the orchestration together.
