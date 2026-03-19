# Sentinel-v2 Gap Analysis: Production Run Logs vs. Spec Coverage

## 1. Bug-by-Bug Coverage Table

| # | Bug/Issue | Run(s) | Sentinel-v2 Coverage | Status |
|---|-----------|--------|---------------------|--------|
| 1 | **opsx:ff → apply not chaining** — after ff creates artifacts, next iteration wastes ~60K tokens reading "ready for apply" but never runs it | v8 (sandbox-polish, company-batch-ops), v9 (deal-kanban, deal-list-view) | NOT in sentinel-v2 scope. This is a wt-loop/dispatch prompt issue, not orchestration modularization. | **MISSING** |
| 2 | **No idle iteration detection** — same 300-byte output repeated 12+ times without stopping | v8 (sandbox-polish 12 iters, company-batch-ops 13 iters) | **Task 3.3** — action hash loop detection (5 consecutive identical hashes → escalation) | **COVERED** |
| 3 | **Smoke auto-fix agent can't diagnose infra config issues** (playwright workers, stale server, Turbopack cache) | v8, v9 (5/7 failures), v10 (3/5 failures), v11 (smoke fix timeout) | NOT addressed. Sentinel-v2 has no smoke fix redesign. The v9 run log contains a detailed design for Ralph-based smoke fix, but sentinel-v2 tasks don't include it. | **MISSING** |
| 4 | **LLM merge conflict resolver fails on additive list conflicts** ("LLM output did not contain any resolved files") | v8 (activity-logger.ts), v10 (activity-logger.ts 2x), v11 (4 i18n files) | NOT directly addressed. Sentinel-v2 has merger.sh extraction (task 1.6) but no merger enhancement tasks for improving the LLM resolver. | **MISSING** |
| 5 | **Orchestrator crashes/exits on merge failure** instead of marking change as merge-blocked | v8 (company-batch-ops), v10 (stale "running" state after SIGINT) | **Partially** — task 9.3 (controlled restart with stale state fix) handles the aftermath, but no task prevents the crash or adds a "merge-blocked" state. | **PARTIAL** |
| 6 | **Orchestrator stalls** — PID alive but no log activity, requires SIGKILL | v11 (2x: tier-enforcement verify stall, i18n-pages-core resume stall) | **Tasks 3.1-3.9** (watchdog) + **Tasks 9.1-9.4** (enhanced sentinel liveness). Core purpose of sentinel-v2. | **COVERED** |
| 7 | **Stale "running" state after crash** — prevents restart ("Orchestrator is already running") | v10 (~14:15) | **Task 9.3** — controlled restart with state cleanup (set status=stopped) | **COVERED** |
| 8 | **Replan duplication** — Phase 4 re-planned changes already done in Phase 1-2 | v10 (copilot-page-context, message-protocol, tool-registry re-planned) | **Task 6.3** — inject git log of completed changes into replanner prompt | **COVERED** |
| 9 | **Parallel changes touching shared files → merge conflicts** (activity-logger.ts, i18n files) | v8, v10, v11 | **Tasks 6.1-6.2** — file-path overlap detection using project-knowledge.yaml cross-cutting file registry | **COVERED** |
| 10 | **Sonnet review fails/timeouts → Opus escalation overhead** (~15 min extra in v11) | v11 (4/8 changes) | **Task 7.1-7.3** — per-change model routing (complexity-based). Does NOT address review model escalation specifically. | **PARTIAL** |
| 11 | **Context bloat in worktrees** (~370K unnecessary files) | v11 (~22:30 observation) | **Tasks 4.1-4.4** — worktree context pruning | **COVERED** |
| 12 | **Post-merge smoke fails because dev server not restarted** / stale Turbopack cache | v9 (5/7 smoke fail), v10 (3/5 smoke fail) | NOT addressed. No health_check or dev server lifecycle management in sentinel-v2. | **MISSING** |
| 13 | **Smoke fix agent scoped to wrong files** — can't fix issues from other changes (cross-change blindness) | v10 (copilot-page-context smoke fix attempted wrong files) | NOT addressed. | **MISSING** |
| 14 | **Scope verify false positive** — flagged "only artifacts merged" despite implementation being present | v10 (copilot-read-tools) | NOT addressed. Verifier enhancements (tasks 8.1-8.4) focus on project-knowledge rules, not scope verify accuracy. | **MISSING** |
| 15 | **Memory/heartbeat audit overhead** (~10 min pure overhead from 200 heartbeats) | v11 | NOT addressed. Heartbeat frequency is not configurable in sentinel-v2. | **MISSING** |
| 16 | **Large CLAUDE.md + design doc imports = slow Ralph iterations** (52K tokens per turn) | v11 (15-25 min per Ralph iteration) | **Partially** — context pruning (task 4) removes orchestrator files but doesn't address CLAUDE.md size or design doc imports. Already mitigated manually in v11 (path-scoped rules). | **PARTIAL** |
| 17 | **Ralph dies/stalls mid-implementation** — orchestrator logs "will auto-resume" but gets stuck in polling loop | v11 (i18n-pages-core, PID 3712006) | **Tasks 3.1-3.2** — watchdog per-state timeout + PID death detection | **COVERED** |

## 2. Production Config Analysis

The sales-raketa `orchestration.yaml` uses these directives:

```yaml
merge_policy: eager
checkpoint_every: 99         # effectively disabled
auto_replan: true
review_before_merge: true
smoke_command: SMOKE_BASE_URL=http://localhost:3002 pnpm test:smoke
smoke_timeout: 120
post_merge_command: pnpm db:generate
```

**Observations:**

- **No `smoke_blocking` directive** — smoke is non-blocking, which the v9 run log explicitly argues should change. Sentinel-v2 does not add this.
- **No `max_parallel` setting** — defaults are used. The v9 conclusions suggest considering `max_parallel: 3`.
- **No `review_model` directive** — v11 documents that Sonnet review is unreliable at scale and recommends `review_model: opus` or configurable escalation.
- **Comments document known bug patterns** from v8 — the config itself has evolved into a living diagnostic document.
- **`post_merge_command`** is used (`pnpm db:generate`) but there is no health check after it. The v9 design specifies `health_check(localhost:PORT, 30s wait, 5s recompile buffer)` — not in sentinel-v2.

## 3. Recurring Patterns (Multi-Run Issues)

| Pattern | Runs Affected | Frequency | Sentinel-v2? |
|---------|--------------|-----------|--------------|
| **LLM merge resolver failure** on additive conflicts | v8, v10 (2x), v11 | 4 occurrences across 3 runs | **NO** |
| **ff → apply chaining bug** | v8 (2x), v9 (2x) | 4 occurrences across 2 runs | **NO** |
| **Smoke failures from stale dev server** | v9 (5x), v10 (3x) | 8 occurrences across 2 runs | **NO** |
| **Orchestrator stalls** (alive but stuck) | v11 (2x) | 2 occurrences in 1 run | **YES** (watchdog) |
| **Smoke fix agent ineffective** | v8, v9, v10, v11 | Every run | **NO** |

## 4. Operator Interventions Analysis

| Intervention | Run | What Happened | Would Sentinel-v2 Handle It? |
|---|---|---|---|
| Manual merge of activity-logger.ts | v8 | LLM resolver failed on additive conflict | **NO** — no merger enhancement in sentinel-v2 |
| SIGKILL of stuck orchestrator | v8 | Orchestrator crashed on merge failure | **YES** — watchdog + sentinel restart (tasks 3, 9) |
| Manual merge of activity-logger.ts (subscription actions) | v10 | Same LLM resolver failure pattern | **NO** |
| Reset stale "running" state via python script | v10 | State stuck after SIGINT | **YES** — sentinel controlled restart cleans state (task 9.3) |
| Manual removal of stale @ts-expect-error | v10 | Cross-change dependency broke build | **NO** — sentinel-v2 has no post-merge build fix capability |
| Manual merge of route.ts comment conflict | v10 | Same LLM resolver pattern | **NO** |
| Start dev server for smoke tests | v10 | Port 3002 not running | **NO** — no dev server lifecycle management |
| Fix Turbopack cache (fuser -k + db:generate + restart) | v10 | Stale Prisma client after schema migration | **NO** — no infra-level recovery |
| SIGKILL of stalled orchestrator (2x) | v11 | Orchestrator stuck after verify, stuck after Ralph exit | **YES** — watchdog + sentinel liveness (tasks 3, 9) |
| Manual 4-file merge conflict resolution (i18n) | v11 | LLM resolver failed on i18n pattern conflicts | **NO** |
| Manual state reset + restart (sentinel) | v11 | Post-stall recovery | **YES** — sentinel controlled restart (task 9.3) |

**Score: Sentinel-v2 would auto-handle 5/11 interventions (45%).** The remaining 6 all involve either LLM merge resolver failures or infrastructure/dev-server issues.

## 5. Performance Data

| Metric | v8 | v9 | v10 | v11 |
|---|---|---|---|---|
| Wasted iterations | ~30 | 2 | ~0 | ~0 |
| Token waste (ff→apply) | ~12.5K | ~120K | 0 | 0 |
| Sentinel restarts | 1 | 0 | 3 | 4 |
| Manual interventions | 2 | 0 | 4 | 1 |
| Smoke fix waste | Unknown | ~100K (5 failed fixes) | 3 timeouts | ~18 min (6x3 min timeouts) |
| Context bloat | Not measured | Not measured | Not measured | 370K in worktrees |
| Wall clock | ~4h+ | ~2h 30m | ~3h | ~3h 55m |

**Sentinel-v2 addresses:** Wasted iterations (watchdog loop detection), context bloat (pruning), orchestrator restarts (watchdog + sentinel).

**Sentinel-v2 does NOT address:** Smoke fix waste (biggest recurring token drain), ff→apply chaining.

## 6. "Conclusions for set-core Development" — Full Extraction

### From v8:
1. opsx:ff → apply not chaining — **MISSING from sentinel-v2**
2. No idle iteration detection — **COVERED** (watchdog task 3.3)
3. Smoke auto-fix can't diagnose infra config — **MISSING**
4. LLM conflict resolver fails on additive conflicts — **MISSING**
5. Orchestrator crashes on merge failure — **PARTIAL** (recovery yes, prevention no)

### From v9:
1. ff → apply chaining still broken — **MISSING**
2. Post-merge smoke fails (stale dev server) — **MISSING**
3. Smoke blocking gate design (detailed, with states, directives, Ralph fix) — **MISSING**
4. Stall detection works (positive) — **COVERED** (expanded in sentinel-v2)
5. Spec quality matters most (observation) — **COVERED** (project-knowledge helps with scope isolation)

### From v10:
1. wt-merge LLM resolver fails on trivial 1-line conflicts — **MISSING**
2. Replan duplication (doesn't check git history) — **COVERED** (task 6.3)
3. Smoke fix agent cross-change blindness — **MISSING**
4. Scope verify false positive — **MISSING**

### From v11:
1. Smoke fix timeout = 100% waste — **MISSING**
2. Sonnet review fail → Opus escalation overhead — **PARTIAL** (model routing exists but not for review)
3. LLM merge resolver fails on i18n conflicts — **MISSING**
4. Sequential dependency chain bottleneck (i18n) — Not a tool bug, spec planning issue. **PARTIALLY** covered by project-knowledge.
5. Orchestrator stalls (2x) — **COVERED** (watchdog)
6. Opus + large CLAUDE.md = slow Ralph — **PARTIAL** (context pruning helps, but doesn't address CLAUDE.md itself)
7. Memory audit overhead — **MISSING**

---

## GAPS: Real Production Issues NOT Addressed by Sentinel-v2

### GAP 1: Smoke Test Pipeline (HIGHEST PRIORITY)

The entire smoke test pipeline is broken in production and sentinel-v2 has zero tasks for it. This was the most impactful issue across all four runs.

**What's needed (designed in v9 run log):**
- Smoke as blocking gate with new states: `merged` → `smoking` → `completed`/`smoke_failed`/`smoke_blocked`
- Health check before smoke (detect no dev server vs code issue)
- Ralph-based smoke fix instead of generic agent (full change context)
- New directives: `smoke_fix_token_budget`, `smoke_fix_max_turns`, `smoke_fix_max_retries`
- Dev server restart after `post_merge_command`

**Evidence:**
> v9: "5/7 changes had smoke_result: 'fail'. The generic LLM fix agent (sonnet, no change context) couldn't diagnose 'stale server' — wasted ~100K tokens on 5 failed fix attempts."
> v10: "Smoke fix agent: all 3 attempts timeout (exit 124), scoped to wrong files."
> v11: "Smoke fix timeout = 100% waste (~18 perc)... A smoke fix agent nem kapott eleg kontextust/idot a problema megertesehez"

### GAP 2: LLM Merge Conflict Resolver (HIGH PRIORITY)

Failed in every run that had merge conflicts (v8, v10, v11). Always the same pattern: "LLM output did not contain any resolved files." Four total occurrences, all requiring manual intervention.

**What's needed:**
- Improved LLM resolver prompt that handles additive conflicts (both sides add to same list/array)
- Fallback strategy: if LLM resolver fails, try simple concat strategy for additive patterns
- "merge-blocked" state so orchestrator continues with other changes instead of crashing

**Evidence:**
> v8: "LLM conflict resolver failed on simple additive conflict... Orchestrator crashed on merge failure instead of marking change as merge-blocked and continuing"
> v10: "wt-merge fails on trivial 1-line conflicts consistently"
> v11: "LLM output did not contain any resolved files" (3 attempts)

### GAP 3: ff → apply Chaining (MEDIUM PRIORITY)

Present in v8 and v9 (4 occurrences total). Self-recovers but wastes ~60K tokens per occurrence. This is a dispatch/wt-loop issue, not orchestration module scope, but it should be tracked somewhere.

**Evidence:**
> v9: "After opsx:ff creates artifacts, the next iteration reads from memory 'artifacts complete, ready for /opsx:apply' but doesn't actually run apply. It wastes 1 iteration (~60K tokens) before self-recovering."

### GAP 4: Review Model Escalation (LOW-MEDIUM)

Sentinel-v2 has per-change model routing (tasks 7.1-7.3) but not review model configuration. v11 found that Sonnet review is unreliable at project scale.

**Evidence:**
> v11: "4/8 change-nel a Sonnet review failelt (timeout vagy rossz output), Opus kellett. Ez ~15 perc extra overhead."

### GAP 5: Scope Verify Accuracy (LOW)

False positive in v10 — flagged implementation as "only artifacts." Not addressed by sentinel-v2 verifier enhancements which focus on project-knowledge rules.

**Evidence:**
> v10: "Scope verify flagged 'only artifacts merged' but implementation was there — false alarm."

### GAP 6: Post-Merge Build Fix (LOW)

v10 required sentinel to manually remove stale `@ts-expect-error` after a cross-change dependency introduced a real module. Sentinel-v2 has no capability for post-merge build repair.

**Evidence:**
> v10: "Sentinel violated guardrails by modifying code files, but pragmatically necessary."

---

## Prioritized Recommendations for Sentinel-v2 Additions

### P0 — Add to sentinel-v2 (blocks production quality)

**1. Smoke Pipeline Redesign (new task group)**
Add tasks for: health check before smoke, blocking gate states (`smoking`/`smoke_failed`/`smoke_blocked`), Ralph-based smoke fix with change context, new directives (`smoke_fix_token_budget`, `smoke_fix_max_turns`, `smoke_fix_max_retries`), dev server health monitoring. The complete design already exists in the v9 run log — it just needs to be converted to tasks.

**2. Merger Enhancement — additive conflict handling + merge-blocked state (extend task group 1.6)**
Add tasks for: improved LLM resolver prompt for additive patterns, concat-based fallback for list/array additions, `merge-blocked` change state so orchestrator continues instead of crashing. This is the second most frequent manual intervention across all runs.

### P1 — Should add (significant token waste)

**3. ff → apply chaining fix (new task, possibly in dispatcher.sh)**
In `dispatch_change()`, after `opsx:ff` completes, explicitly chain `opsx:apply` in the next dispatch prompt. Alternatively, modify `opsx:ff` itself to invoke `opsx:apply`. This is a dispatcher enhancement that fits naturally in task group 10 (Dispatcher Enhancements).

**4. Review model configuration (extend task 7)**
Add `review_model` directive and Sonnet → Opus escalation logic to the verifier. When Sonnet review fails/timeouts, auto-escalate to Opus without counting as a verify failure.

### P2 — Nice to have

**5. Heartbeat frequency configuration** — make memory audit interval configurable to reduce log noise.

**6. Scope verify improvements** — reduce false positives in the implementation completeness check.
