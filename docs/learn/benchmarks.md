# Benchmarks

Consolidated results from E2E orchestration runs — real applications built autonomously from spec to production-ready code.

---

## MiniShop — Autonomous Webshop

The hero benchmark: a Next.js 14 e-commerce storefront built with zero human intervention.

The sentinel received a product spec describing a webshop with product listings, cart, checkout, admin authentication, and admin CRUD. It decomposed the spec into 6 changes with a dependency graph, dispatched each to a worktree agent, ran quality gates on every change, and merged all results to main.

| Metric | Value |
|--------|-------|
| Changes planned | 6 |
| Changes merged | 6/6 (100%) |
| Wall clock time | 1h 45m |
| Active build time | ~1h 25m |
| Human interventions | 0 |
| Merge conflicts | 0 |
| Jest unit tests | 38 (6 suites) |
| Playwright E2E tests | 32 (6 spec files) |
| Git commits | 39 |
| Total tokens | 2.7M |
| Gate retries | 5 (all self-healed) |

The 5 retries included a missing test file (agent added it), a Jest config issue (agent fixed it), failing Playwright auth tests (agent fixed 3 specs), a post-merge type error (agent resolved after main sync), and a cart test race condition (agent fixed timing). No retry required human help.

**The built storefront:**

![Product listing page](../images/auto/app/products.png)

**Dashboard showing all 6 changes merged:**

![Dashboard changes tab](../images/auto/web/tab-changes.png)

---

## What Gets Built

The orchestrator produces a complete, working application — not scaffolding or stubs. These screenshots were captured automatically from the running app after all changes merged.

| Page | Screenshot |
|------|-----------|
| Product listing | ![products](../images/auto/app/products.png) |
| Product detail | ![product-detail](../images/auto/app/product-detail.png) |
| Admin dashboard | ![admin](../images/auto/app/admin.png) |
| Admin login | ![admin-login](../images/auto/app/admin-login.png) |

Every page includes working data from a seeded database, functional navigation, and responsive layout. The admin panel has full CRUD for products, protected by authentication middleware.

---

## Quality Gate Results

Every change passes through a multi-stage verification pipeline before it is allowed to merge into main:

```
Agent completes --> Jest --> Build --> Playwright E2E --> Verify (OpenSpec) --> Merge --> Post-merge smoke
```

No change reaches main without green gates. The verify step checks spec coverage — ensuring the agent actually implemented what the planner specified, not just code that happens to build.

![Phases tab showing gate progression](../images/auto/web/tab-phases.png)

In the MiniShop run, total gate execution time was 422 seconds (12% of active build time). The gates caught 5 issues that agents then fixed autonomously. Without gates, those 5 issues would have merged broken code into main and cascaded into downstream changes.

---

## Token Usage

Token consumption across all 6 MiniShop changes:

![Token usage chart](../images/auto/web/tab-tokens.png)

| Change | Input | Output | Cache Read | Total |
|--------|-------|--------|------------|-------|
| project-infrastructure | 367K | 42K | 12.3M | 410K |
| products-page | 378K | 28K | 7.2M | 406K |
| cart-feature | 460K | 39K | 12.6M | 499K |
| admin-auth | 329K | 41K | 10.5M | 370K |
| orders-checkout | 312K | 36K | 10.5M | 348K |
| admin-products | 568K | 87K | 18.3M | 655K |
| **Total** | **2.4M** | **273K** | **71.4M** | **2.7M** |

The `admin-products` change consumed the most tokens (655K) because it was the last in the dependency chain and required the most context about existing code. Cache read tokens (71.4M) reflect prompt caching — the same project context is reused across turns within each agent session, keeping actual billed tokens low.

Average cost per change: ~450K tokens. For a 6-change project, this is roughly equivalent to 3-4 hours of manual senior developer work compressed into 1h 45m of wall clock time.

---

## Scale: MiniShop vs CraftBrew

The CraftBrew run (15 changes, 150+ source files, 28 database tables) tested the system at 2.5x the scale of MiniShop. It completed all 15 changes but exposed merge conflict handling as the key scaling bottleneck — cross-cutting files like Prisma schemas caused data loss during manual conflict resolution. This directly drove the development of automated conflict detection and cross-cutting file protection in subsequent engine versions.

| Metric | MiniShop | CraftBrew | Factor |
|--------|----------|-----------|--------|
| Changes | 6 | 15 | 2.5x |
| Source files | 47 | 150+ | 3x |
| DB models | ~8 | 20+ | 2.5x |
| Merge conflicts | 0 | Multiple | -- |
| Human intervention | 0 | Required | -- |

---

<!-- specs: verify-gate, orchestration-engine, dispatch-core -->
