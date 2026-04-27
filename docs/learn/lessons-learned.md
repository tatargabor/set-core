[< Back to Index](../INDEX.md)

# Lessons Learned — Production Insights

Key insights from 60+ autonomous orchestration runs across real projects (MiniShop, CraftBrew, MicroWeb, CraftBazaar). Each lesson was learned the hard way — through failures that cost hours of compute, corrupted branches, wasted overnight runs, or — in one case — a 10× billing inflation that hid in plain sight for weeks.

---

## 1. Agents Need Structure, Not Just Prompts

Without OpenSpec artifacts, agents drift — they skip requirements, make inconsistent architecture decisions, and produce code that doesn't match the spec. In early CraftBrew runs, we told agents "build an admin dashboard with CRUD for products." The result: three different agents chose three different table libraries, two skipped pagination entirely, and one implemented delete but not edit.

The proposal -> specs -> design -> tasks pipeline keeps them focused. Each agent gets a proposal with explicit scope boundaries (IN SCOPE / OUT OF SCOPE). Task lists link back to spec requirements with `[REQ: ...]` tags. The verify gate checks that every requirement has corresponding code — not just that tests pass, but that the agent built what was asked.

**Before:** "Build the cart feature" -> agent produces cart with no price calculation, no empty-cart state, no persistence.
**After:** Proposal lists 8 requirements, tasks reference each one, verify gate checks all 8 -> agent implements all 8.

---

## 2. Quality Gates Must Be Deterministic

Early versions used LLM-judged code review as a merge gate. The result: inconsistent pass/fail decisions, agents gaming the reviewer (adding verbose comments that made code "look good"), and false positives that let bugs through. In CraftBrew run #3, an LLM review passed code with a hardcoded `TODO: implement later` that broke the checkout flow.

**What we did:** Made test, build, and E2E gates deterministic — exit code 0 or not. A failing Jest test is unambiguous. A `next build` that exits with code 1 cannot be talked past. Only the spec-coverage review remains LLM-based, with explicit PASS/FAIL parsing and a separate lint gate using pattern matching (grep for forbidden patterns like `console.log`, hardcoded secrets, `any` types) rather than LLM judgment.

**The gate pipeline in order:**
```
Jest (8s) -> Build (35s) -> Playwright E2E (45s) -> Spec Verify (25s) -> Post-merge Smoke (15s)
```

Fast gates run first. If Jest fails, the agent never waits for a 45-second Playwright run.

---

## 3. Merge Conflicts Are the #1 Cascading Failure

When 5 changes merge simultaneously, each failed ff-only merge triggers a full re-gate cycle (build + test + review). In CraftBrew run #4, three changes all modified the Prisma schema — `products`, `orders`, and `i18n`. The first merge succeeded. The second caused a conflict in `schema.prisma`. The third conflicted with both. Each retry took 3 minutes of gate time. The cascade cost 45 minutes of wasted compute.

Cross-cutting files cause the most damage: Prisma schemas, i18n message bundles, middleware chains, route registrations, and shared type definitions.

**What we did:**
- **Phase-ordered execution** — changes in phase 2 only start after all phase 1 changes merge. This guarantees that phase 2 agents see the latest main.
- **Dependency DAG** — the planner explicitly declares which changes depend on which. `cart-feature` depends on `product-model`, so cart never starts until products is merged.
- **Automatic main integration** — before attempting ff-only merge, the engine merges main into the branch and re-runs gates. This catches conflicts before they reach main.
- **Sequential merge queue** — even within a phase, merges happen one at a time. No parallel merges, ever.

---

## 4. Memory Without Save Hooks Is Useless

Across 15+ agent sessions in the CraftBazaar memory benchmark, agents made **zero voluntary memory saves**. Not one. They're too focused on the immediate task — writing code, fixing tests, reading errors — to remember to save context for future sessions. When explicitly instructed to "save important learnings to memory," they acknowledged the instruction and then never did it.

**What we did:** Built 5-layer hook infrastructure that operates without agent cooperation:
1. **Session boundary hooks** — automatically extract and save key decisions when an agent session starts or ends
2. **Post-tool-call hooks** — after file reads and bash commands, relevant past experience is injected into the conversation
3. **Error hooks** — when a tool call fails, past fixes for similar errors are surfaced automatically
4. **Transcript extraction** — raw conversation transcripts are filtered for insights after each session
5. **Branch-aware tagging** — memories are tagged with the worktree/branch they came from, so recall is context-aware

The CraftBazaar benchmark showed **+34% weighted improvement** with this infrastructure enabled — agents made fewer repeated mistakes and converged on solutions faster.

---

## 5. E2E Testing the Orchestrator Reveals Bugs No Unit Test Catches

Unit tests for the orchestrator all pass. Every module works correctly in isolation. But real orchestration runs fail — because the interactions between digest, planner, dispatcher, verifier, and merger create emergent behaviors that only surface when all components run together against a real codebase.

Bugs found only through E2E runs:
- **Stale lock files** — the orchestrator crashed, leaving a lock file that prevented restart. Unit tests never create lock files.
- **Zombie worktree processes** — an agent process outlived its worktree deletion. The PID was recycled and the cleanup script killed an unrelated process.
- **Race condition in poll cycle** — the monitor polled at 15-second intervals. An agent completed at second 14. The completion event was processed, but the next poll (1 second later) saw stale state and re-dispatched the same change.
- **Token tracking overflow** — token counts stored as 32-bit integers overflowed at 10M+ cache read tokens, producing negative values in the dashboard.
- **Watchdog false positive during pnpm install** — `pnpm install` can take 60+ seconds with no stdout. The watchdog interpreted this as a stall and killed the agent.

**What we did:** Built a full E2E test infrastructure (`tests/e2e/runners/run-minishop.sh`, `run-micro-web.sh`, `run-craftbrew.sh`) that scaffolds a real project, runs the complete orchestration pipeline, and validates results. Each E2E run produces a benchmark report. We run micro-web (fastest, ~20 min) on every framework change and minishop/craftbrew on release candidates.

---

## 6. Stall Detection Needs Grace Periods

Agents go silent during large file writes, Prisma migrations, `pnpm install`, or MCP server fetches. The watchdog sees no stdout for 60 seconds and concludes the agent is stalled. In CraftBrew run #2, the watchdog killed an agent that was 90% through a Prisma migration — the resulting half-applied migration corrupted the database schema and required manual cleanup.

**What we did:** Added expected-pattern awareness to the watchdog:
- **Package install** — if the last stdout line contains `pnpm`, `npm`, or `yarn`, extend timeout to 120 seconds
- **Post-merge codegen** — after a merge event, extend timeout to 90 seconds (Prisma generate, type generation)
- **MCP fetch** — if the agent is calling an MCP tool, extend timeout to 60 seconds
- **Large file write** — if the agent's last action was a file write > 500 lines, extend timeout to 45 seconds

The watchdog also uses a graduated escalation chain: first warning (log only), second warning (inject "are you stuck?" message), third warning (force checkpoint and pause). Kill is the last resort, not the first response.

---

## 7. The Sentinel Pays for Itself

A single undetected crash at 2 AM wastes the entire overnight run. In the pre-sentinel era (runs #1--2), we lost 3 overnight runs to undetected crashes — the orchestrator segfaulted, the machine ran out of disk, or a network timeout killed the LLM connection. Each wasted run cost 4--6 hours of compute.

The sentinel costs ~5--10 LLM calls per run (for decision-making about restarts, stall diagnosis, and replan triggers) but saves hours of wasted compute by detecting and recovering from crashes within 30 seconds.

**What the sentinel catches:**
- **Orchestrator crash** — detects missing PID, reads last log lines, diagnoses cause, restarts with state recovery
- **Agent stall cascade** — when multiple agents stall simultaneously (usually a shared resource issue), the sentinel pauses all agents, fixes the resource, and resumes
- **Disk space** — monitors available disk and pauses orchestration before running out (learned from a run where 50GB of node_modules filled the drive)
- **Merge queue deadlock** — detects when the merge queue has been stuck for > 10 minutes and triggers investigation

The three-tier supervision model (sentinel -> orchestrator -> agents) means each layer only needs to handle its own failure modes. Agents handle code errors. The orchestrator handles workflow errors. The sentinel handles infrastructure errors.

![Sentinel tab showing supervision decisions](../images/auto/web/tab-sentinel.png)

---

## 8. Templates Beat Conventions

Telling 5 agents "create a Next.js project with Prisma and Tailwind" produces 5 different directory structures, 5 different config file formats, and 5 different naming conventions. Even with detailed instructions, agents make different choices about where to put components, how to name files, and which config options to set.

The three-layer template system reduced file structure divergence from 63% to 0%:

1. **Core templates** (`templates/core/`) — universal rules deployed to every project (file size limits, secret detection, todo tracking)
2. **Module templates** (`modules/web/templates/`) — project-type-specific structure (Next.js app router layout, Prisma schema location, test directory structure)
3. **Project templates** — initialized by `set-project init` with concrete files, not just instructions

**Before templates:** Agent A puts components in `src/components/`, Agent B puts them in `app/components/`, Agent C puts them in `components/`. Merge conflicts everywhere.
**After templates:** All agents find `src/components/` already exists with an example component. They follow the established pattern. Zero structural conflicts.

---

## 9. Cost Is a First-Class Metric

For weeks, the dashboard reported orchestration cost in USD using a formula that included `cache_read_input_tokens` in the input total. This was wrong — Anthropic bills `cache_read` at a different rate than fresh input — and the bug inflated reported cost by roughly 10×. It hid because nobody was treating the line as load-bearing; the dashboard rendered it, the line moved when expected, no alarm fired.

**What we did:** Subtracted `cache_read_input_tokens` from the input total before applying the input-rate, added per-section breakdown to `input.md` so the dispatcher's prompt size is visible per section (instructions, scope, design, retry context), wrote a duplicate-read detector that flags the same file being Read twice within one iteration, and surfaced USD per change / per gate / per session as a first-class column on the dashboard. The `set-run-logs` CLI emits the same numbers in JSON for offline analysis.

**The lesson generalizes.** Whenever a metric is computed, displayed, but not actively monitored, it will quietly drift. The fix is not "compute more carefully" — it's "make the metric load-bearing for a decision somewhere." Cost now drives the per-change token-runaway breaker (50M token ceiling, 80% pre-warning); a wrong cost number would now cause a wrong decision and surface immediately.

---

## 10. Circuit-Breakers Beat Retries

Early retry loops were unbounded — "if the gate fails, redispatch the agent" with no global ceiling. Production runs found three pathological loops: a poisoned-stall pattern where the agent re-encountered the same hash; a merge-stalled pattern where ff-only retries kept failing because the branch was rebuilt with the same conflict; and a token-runaway where an agent's session inflated past 50M tokens before anyone noticed.

**What we did:** Wrapped each retry source in a circuit-breaker with an explicit escalation path. `merge_stalled` after 6 FF failures → `failed:merge_stalled` → `escalate_change_to_fix_iss(escalation_reason="merge_stalled")` → `IssueRegistry` registers a circuit-breaker issue → investigator agent diagnoses → resolver fixes → parent change auto-recovers from `failed:*` and re-dispatches on a clean worktree. `token_runaway` and `poisoned_stall` follow the same pattern with their own thresholds. Cleanup of on-disk worktree + `change/<name>` branch happens BEFORE the in-memory state reset, so retry starts on a fresh tree.

The hard part wasn't the circuit-breaker — it was choosing where the escalation went. Sending it to a human creates a backlog. Sending it to an investigator agent creates a self-healing loop, but only if the investigator can produce a structured diagnosis the resolver can act on. The fix-iss pipeline became the universal escalation target because it was already the only path that produced verifiable, scoped fixes.

---

## 11. Design as Code, Not as Image

The Figma `.make` design pipeline shipped in Phase 8 had three real failure modes that no amount of patching could fix. Binary `.make` files were 3.9 MB ZIPs that couldn't be diffed; reviewers couldn't tell why a token changed between revisions. Figma's color naming (`color-muted`) collided with shadcn primitive pairs (`--muted` / `--muted-foreground`); the parser produced identical values for both, causing invisible text in tabs and sidebar labels. Figma frames didn't define interactive states (hover, selected, disabled, focus), so the agent had nothing to bind against.

**What we did:** Replaced the entire upstream. v0.app generates shadcn/ui + Tailwind + Next.js code natively — the export IS the design source. `set-design-import` clones a v0 repo, generates `design-manifest.yaml` with shell components, routes, and component bindings. The dispatcher writes a per-change `design.md` slice into each agent's input. The `design-fidelity-gate` runs a JSX structural parity check on every UI change — if the agent diverges from the v0 export's component structure or tokens, merge is blocked and a diff is emitted.

**The lesson generalizes.** Sources you can't diff hide their semantics. When the agent and the human read different artifacts, the artifact agent reads becomes the truth — make sure that's the artifact you can review.

---

## 12. Manual Override Beats Automation at Destructive Boundaries

The sentinel happily auto-recovers from most failures: stuck states, dead PIDs, integration conflicts. But one early experiment let it auto-reset the entire orchestration when the spec changed mid-run. This deleted 3 hours of completed work because the sentinel decided "spec changed → start over." The reset was reversible only because git history preserved the merged commits.

**What we did:** Drew a hard line: any operation that destroys state (spec reset, recovery rollback, change archive with completed work) requires explicit human approval. The sentinel surfaces a banner; it does not act. Auto-recovery is bounded to in-memory state changes and on-disk artifacts that can be regenerated from spec+main. Anything that touches commits or removes finished work is operator-gated.

**The lesson generalizes.** Automation should expand the floor of competence (the system handles routine failures without you), not the ceiling of authority (the system decides when to throw work away). Match each automation tier to its blast radius.

---

*See also: [Benchmarks](benchmarks.md) · [Journey](journey.md) · [How It Works](how-it-works.md)*

<!-- specs: orchestration-watchdog, sentinel-polling, gate-profiles, hook-driven-memory -->
