## 1. Benchmark Directory Structure

- [x] 1.1 Create `benchmark/` directory at project root
- [x] 1.2 Create `benchmark/README.md` with overview, purpose, and quick-start instructions
- [x] 1.3 Create `benchmark/claude-md/` directory for CLAUDE.md variants
- [x] 1.4 Create `benchmark/changes/` directory for per-change definitions
- [x] 1.5 Create `benchmark/templates/` directory for annotation and report templates

## 2. Project Specification

- [x] 2.1 Create `benchmark/project-spec.md` — full CraftBazaar domain description (business context, tech stack, core entities, feature overview) without implementation hints or trap reveals

## 3. Change Definitions

Each change file has two sections separated by a `<!-- EVALUATOR NOTES BELOW — NOT INCLUDED IN AGENT INPUT -->` marker. The "Agent Input" section above the marker is what gets extracted into the project repo. The "Evaluator Notes" section below stays in set-core only.

- [x] 3.1 Create `benchmark/changes/01-product-catalog.md` — Agent Input: product model with variants (size/color/material), CRUD API routes, seed data, acceptance criteria. Evaluator Notes: trap docs (T1.1 variant modeling decision, T1.2 Prisma generate sequence, T1.3 image handling), memory predictions, scoring focus
- [x] 3.2 Create `benchmark/changes/02-shopping-cart.md` — Agent Input: cart CRUD, variant-level stock tracking, stock reservation, cart total calculation. Evaluator Notes: trap docs (T2.1 SQLite BUSY/WAL mode, T2.2 cart must reference variant not product, T2.3 stock validation race condition), memory predictions
- [x] 3.3 Create `benchmark/changes/03-multi-vendor.md` — Agent Input: vendor model, product-vendor association, order creation from cart, per-vendor sub-orders. Evaluator Notes: trap docs (T3.1 flat vs nested order architecture — THE pivotal decision, T3.2 Prisma migration on existing data, T3.3 API redesign cascade), memory predictions
- [x] 3.4 Create `benchmark/changes/04-discounts.md` — Agent Input: coupon CRUD, percentage/fixed discounts, vendor-specific coupons, min order rules. Evaluator Notes: trap docs (T4.1 discount scope confusion — variant vs product level, T4.2 coupon + multi-vendor interaction, T4.3 Prisma Decimal precision in SQLite), memory predictions
- [x] 3.5 Create `benchmark/changes/05-checkout.md` — Agent Input: checkout flow, Stripe test mode integration, tax calculation, multi-vendor payout split. Evaluator Notes: trap docs (T5.1 Stripe env setup — .env.local for Next.js, T5.2 payout + discount interaction, T5.3 SQLite BUSY redux under checkout), memory predictions
- [x] 3.6 Create `benchmark/changes/06-order-workflow.md` — Agent Input: state machine per sub-order (pending→confirmed→shipped→delivered), vendor dashboard, buyer tracking. Evaluator Notes: trap docs (T6.1 state machine depends on C3 order architecture, T6.2 transition validation, T6.3 Next.js App Router + SSE patterns), memory predictions

## 4. CLAUDE.md Variants

Both variants share a common base. The self-directing "Benchmark Task" section is in both. PORT differs (3000 vs 3001).

- [x] 4.1 Create `benchmark/claude-md/baseline.md` — common sections: project setup (Next.js + Prisma + SQLite), testing commands, OpenSpec workflow guidance, dev server port (PORT=3000), self-directing benchmark task section (check openspec list, read next change from docs/benchmark/, use opsx:ff → opsx:apply, write results/change-0N.json). NO memory hooks, NO proactive memory section
- [x] 4.2 Create `benchmark/claude-md/with-memory.md` — identical to baseline except: dev server port (PORT=3001), PLUS proactive memory section (recall before major work, save on insights/errors/decisions, agent self-reflection on session end)

## 5. Scoring and Evaluation

- [x] 5.1 Create `benchmark/scoring-rubric.md` — per-change metrics (dead ends 0-5, repeated mistakes 0-3, design rework 0-3, first-try test pass, session length in iterations+tokens), Run B memory metrics (recalls, useful recalls, saves), concrete scoring examples per level
- [x] 5.2 Create `benchmark/diagnostic-framework.md` — memory gap categories (missed recall, low-quality save, missing memory type, timing issue, recall relevance problem), per-gap documentation template, improvement recommendation format

## 6. Templates

- [x] 6.1 Create `benchmark/templates/session-annotation.md` — per-change annotation template with all metric fields, qualitative notes section (dead ends observed, repeated mistakes, design rework instances), memory event log section (Run B only: recalls and their usefulness, saves)
- [x] 6.2 Create `benchmark/templates/change-metrics.json` — structured JSON template for per-change data: `{change, run, completed, iterations, tokens, commits, time_minutes, dead_ends, repeated_mistakes, design_rework, first_try_pass, memory_recalls, useful_recalls, memories_saved}`
- [x] 6.3 Create `benchmark/templates/comparison-report.md` — side-by-side aggregate table (Run A vs Run B), per-change detail rows, delta calculations (absolute + percentage), narrative findings section, diagnostic summary section, memory gap analysis section

## 7. Run Guide

- [x] 7.1 Create `benchmark/run-guide.md` — complete step-by-step execution guide with these sections:
  - **Prerequisites**: set-core installed and on PATH, Node.js 18+, Claude Code CLI, enough disk/RAM for two parallel Next.js projects
  - **Directory setup**: create `~/benchmark/run-a/` and `~/benchmark/run-b/`
  - **Bootstrap Run A**: `git init craftbazaar && cd craftbazaar`, `openspec init --tools claude`, `wt-deploy-hooks .`, extract agent-only change files to `docs/benchmark/`, copy `baseline.md` as CLAUDE.md, initial git commit
  - **Bootstrap Run B**: same as Run A but additionally `set-memory-hooks install`, copy `with-memory.md` as CLAUDE.md (with PORT=3001)
  - **Change file extraction**: how to split change definitions at the marker line and copy only "Agent Input" sections to `docs/benchmark/`
  - **Starting runs**: `wt-loop start "Build CraftBazaar changes 01-06" --max 20 --stall-threshold 3` in each repo
  - **Monitoring**: `wt-loop monitor` or `wt-loop status` to check progress
  - **No intervention policy**: do not provide hints, answers, or direction. If agent asks a yes/no question, the loop auto-continues. If the loop stalls, record it as data
  - **Results collection**: after both runs complete, how to gather data — `wt-loop history`, `git log --stat`, `openspec list --json`, copy `.claude/ralph-loop.log`, `set-memory list --json` (Run B only)
  - **Post-run annotation**: review transcripts using scoring rubric, fill session-annotation templates, fill change-metrics.json per change
  - **Comparison report**: use comparison-report template to aggregate and compare results

## 8. Results Collection

- [x] 8.1 Create `benchmark/collect-results.md` — a guide (or prompt) for a post-run Claude session that reads both repos' data (wt-loop history, git logs, ralph-loop.log, results/*.json, set-memory list) and generates the comparison report. This enables evaluation to also be agent-assisted rather than fully manual
