# Decompose / Replan Token & Stability Optimization — 2026-05-08

Optimization plan for the planning subsystem after the consumer-d and set-designer runs of 2026-05-07. Builds on `token-optimization-analysis-2026-04-09.md` (which covered agent-side cost) — this one covers the **planner-side** cost (digest → decompose → replan → merge).

## Executive Summary

The planning pipeline currently:

1. Re-runs the digest from scratch on every cycle, even when the spec is unchanged.
2. Sends the planner prompt to Claude **without `cache_control` directives**, so prefix caching is never declared.
3. Triggers a full re-decompose on AMB / e2e-failure / coverage-gap signals, even when only a slice is invalidated.
4. Uses a `ThreadPoolExecutor` to fan out per-domain decompose calls (Phase 2) without backpressure or retry budget — this is the "merg-es külön szálas decompose" the user reported as unstable.
5. Re-merges Phase 2 outputs in a synchronous Phase 3 Claude call with a 30-min timeout and ~80–120k token context — the largest single LLM call in the pipeline.

Concrete observations from the 2026-05-07 runs:

- **set-designer**: 24 changes planned, 1 ran. The single agent burned **2.39M uncached input tokens + 3.23M cache_read tokens in 7 minutes** before being SIGTERM'd at the spec_verify retry. The orchestrator never replanned (plan_version stayed 1) but the *agent* re-read the same context every iteration with no breakpoint cache.
- **consumer-d**: 5 full digest cycles in ~3 hours, no DISPATCH events. Memory hygiene latency grew from 318 ms (29 entries) to 3363 ms (200 entries) — linear scan on every poll. A "flash digest" at 22:32 finished in 1 second and dropped req_count from 76 → 41 (suspicious — probably partial output silently accepted).
- **53 `LineagePaths fallback`** debug lines in the 7-min set-designer window — ~7/min, one per poll cycle × 3 path lookups, all looking for a lineage-suffixed file/dir that does not exist. Pure I/O waste.
- **No prompt caching declared** in `templates.py:render_planning_prompt`, `_phase1/_phase2/_phase3_*` prompts, or `_DIGEST_PROMPT_TEMPLATE`. Every Claude call rebuilds the whole prefix.

The optimization plan below is organised by impact tier. **No item compromises gap analysis** — `coverage.json` and `triage.md` are produced by the digest, and every proposal preserves the digest as the single source of truth for completeness.

---

## 1. Diagnosis (data)

### 1.1 set-designer — single change, never merged

| Metric (shared-type-definitions) | Value |
|---|---:|
| Wall-clock | 6 m 55 s (22:05–22:12) |
| `tokens_used` | 17,660 |
| `input_tokens` | **2,393,623** |
| `output_tokens` | 17,586 |
| `cache_read_tokens` | **3,231,400** |
| `cache_create_tokens` | 173,266 |
| Iterations until SIGTERM | ~3 (running → done → verify_failed → retry → killed) |

Result: the agent's prefix grew unbounded across iterations (each retry re-injected feedback + previous artifacts), but no breakpoint was set, so cache_read/cache_create churned. spec_verify CRITICAL fired ("ErrorCode union exhaustiveness — 8 codes missing"), retry triggered, supervisor SIGTERM'd at 22:13.

The orchestrator itself never replanned. Plan was generated once at 22:05:48 with `plan_method=api`, 24 changes for `docs/v1-set-designer.md`. Phase pipeline: brief (Phase 1) → 13 parallel domain decomposes (Phase 2) → merge (Phase 3) — all completed cleanly.

### 1.2 consumer-d — digest treadmill

```
20:15:25  DIGEST → 34 reqs, 9 domains   (3m 23s)
20:41:11  DIGEST → 48 reqs, 8 domains   (3m 31s)
21:02:29  DIGEST → 56 reqs, 8 domains   (3m 44s)
22:12:27  DIGEST → 76 reqs, 6 domains   (3m 14s)
22:32:12  DIGEST → 41 reqs, 6 domains   (1 s)   ← suspicious
22:41:38  DIGEST_STARTED (no COMPLETE in window)
23:02:18  DIGEST_STARTED (no COMPLETE in window)
```

Five digests, no DISPATCH events, req_count oscillating 34→76→41. Each digest is a fresh Claude call against the full spec corpus — the on-disk content-addressed cache (`~/.cache/set-orch/digest-cache/`) only hits when prompt+model hash matches exactly, so any spec/memory change misses. Memory hygiene grows linearly: 318 ms @ 29 entries → 3363 ms @ 200 entries — full O(n) scan.

### 1.3 Codebase findings (verified by Explore)

- `lib/set_orch/planner.py` — 3008 lines. Master entry `run_planning_pipeline()` (2535–2739).
- `lib/set_orch/templates.py:render_planning_prompt()` (591–782) — 200-line prompt + 113-line `_PLANNING_RULES_CORE` (390–502). **No `cache_control`.**
- Phase pipeline:
  - `_phase1_planning_brief()` (2108–2160) — 1 Claude call (model `decompose_brief`).
  - `_phase2_parallel_decompose()` (2250–2301) — `ThreadPoolExecutor(max_workers=min(domains, 6))`, one Claude call per domain. **No retry budget per worker, no per-domain timeout, no graceful degradation if k workers fail.**
  - `_phase3_merge_plans()` (2304–2353) — single sync Claude call, 30-min timeout, all domain plans concatenated as markdown blocks (~80–120k tokens).
- `lib/set_orch/digest.py:call_digest_api()` (339–408) — disk cache keyed on `sha256(prompt+model)`. LRU 64 entries. **Does not survive a spec edit.**
- `lib/set_orch/engine.py:_auto_replan_cycle()` (3636–3866) — handles 5 trigger types. Selective by domain only when `input_mode==digest` AND saved `domains-plans-*.json` exists. Otherwise full re-decompose.
- `lib/set_orch/paths.py:451, 562` — the `LineagePaths fallback` log lines. Triggered every time the engine asks for a lineage-suffixed file that doesn't exist on disk. Re-run on every poll cycle.

### 1.4 What "merg-es külön szálas decompose" refers to

It is not a `git merge`-time background thread — `merger.py` is fully synchronous and runs on the main monitor loop. The threaded path is **Phase 2 of the decompose itself**: `_phase2_parallel_decompose` fans out one Claude call per domain via `ThreadPoolExecutor`. When any worker fails, partial dict fallback fills in zero changes for that domain (planner.py:2294–2298), the merge phase sees a hole, and Phase 3 either re-emits the missing domain inline (extra tokens) or silently drops it (gap-analysis risk). That is the source of the instability.

---

## 2. Root causes (categorised)

| ID | Root cause | Evidence | Impact |
|---|---|---|---|
| **R1** | No `cache_control` on planner / digest / Phase 1–3 prompts | `grep cache_control lib/set_orch/templates.py` → 0 hits | Every Claude call pays full input rate; on a 24-change run with 13 domains, that's ~6× $0.50–1.00 calls. |
| **R2** | Digest re-runs from scratch on every cycle | 5 digests in 3 hours, consumer-d | ~3 m of Claude time × 5 = 15 m of pure rework when the spec didn't change |
| **R3** | Phase 2 ThreadPoolExecutor lacks retry / backpressure / partial-success policy | planner.py:2250–2301, no `try/except` per future, no per-worker timeout knob | Failed workers leave silent gaps; planner accepts empty-domain decomposes; user-visible instability |
| **R4** | Phase 3 merge prompt scales O(domain_count × scope_size) | 80–120 k tokens for 6 domains × 50 changes; 30-min timeout | One bad domain plan can OOM the merge; partial-parse fallback exists but is fragile (planner.py:2770–2787) |
| **R5** | Replan trigger model is reactive, not bounded | `_handle_auto_replan` retries on AMB / coverage_gap / e2e_failure with cap=2 cycles, 5 retries — but each retry re-runs full Phase 1+2+3 | A 2-cycle replan on a 13-domain spec ≈ 2 × (1 brief + 13 domain + 1 merge) Claude calls = 30 LLM calls before user sees a result |
| **R6** | AMB resolution coupled to replan | `_build_digest_content` 1653–1672 injects deferred ambiguities into every planner prompt | If the planner can't auto-resolve, AMB persists, replan fires, AMB persists again → the loop the user complained about |
| **R7** | `LineagePaths fallback` re-checks missing files every poll | paths.py:451, 562; 53 hits in 7 min | Cumulative I/O + log noise; not expensive but indicates a missing memoization |
| **R8** | Memory hygiene scans grow linearly | consumer-d: 318 ms → 3363 ms over 3 h | O(n) on every poll — at 1000 entries this becomes ~15 s and starves the monitor loop |
| **R9** | `enrich_plan_metadata` re-scans the lineage archive JSONL on every decompose | planner.py:1766–1783, sequential | Background fixed cost per decompose, scales with archive size |
| **R10** | `compute_phase_offset` and digest-related path fallbacks not memoized within a poll | engine + paths | 4–5 lookup operations × 17 polls × 2 projects = ~170 redundant calls per hour |

---

## 3. Optimization plan (prioritized)

### Tier A — Land in week 1 (highest ROI, low risk)

**A1. Add layered prompt caching to all planner / digest prompts.**
Affected: `templates.py:render_planning_prompt`, `render_brief_prompt`, `render_domain_decompose_prompt`, `render_merge_prompt`, `_DIGEST_PROMPT_TEMPLATE`. Refactor each to return a *list of content blocks* (system / project-rules / digest-stable / spec-tail) instead of a single string. Set 4 breakpoints:

```
BP1 (1h TTL): tools schema + JSON output skeleton
BP2 (1h TTL): system role + _PLANNING_RULES_CORE + project conventions
BP3 (5m TTL): digest stable section (requirements.json, conventions.json, domains/*.md ≤ N most-relevant)
BP4 (uncached): spec tail / replan delta / current cycle's volatile context
```

The Phase 2 domain prompt only needs BP1+BP2 cached (those are identical across all 13 parallel calls); BP3 differs per domain. So the parallel fan-out inherits 100 k+ tokens of cache hits. Anthropic's 1h prefix-cache cost (2× write, 0.1× read) breaks even at ~5 reads — we exceed that on every multi-phase decompose.

Expected impact: **5–10× input-token reduction on the planner prompts**. Direct mapping to the 2.4 M token observation: ~80 % is prefix that should be cached.

**A2. Memoize `LineagePaths` resolution per poll cycle.**
Wrap `paths.py:LineagePaths.{plan_path, digest_dir}` in `functools.lru_cache(maxsize=64)` keyed on `(state_file, lineage_id, request_kind)`. Invalidate at end of each `monitor_loop` iteration. Eliminates the 53 fallback log lines per 7-min window. Trivial change, no behaviour difference.

**A3. Cache `compute_phase_offset` and lineage-archive scan within a planner pipeline.**
`planner.py:1732–1785` is called once per `enrich_plan_metadata` and walks the JSONL archive. Build an index file `set/orchestration/lineage-index.json` with `{spec_lineage_id: max_phase}` updated when archive entries are added. Fall back to full scan on first call after archive mutation.

**A4. Index-based memory hygiene.**
`shodh-memory` should keep a sorted-by-id cache so duplicate detection is O(1) lookup, not O(n) scan. The consumer-d data shows the scan dominates the poll cycle once memory crosses ~150 entries. Either move hygiene off the poll path (separate background sweep, every 10 polls) or rebuild the index incrementally on remember/forget.

**A5. Demote `LineagePaths fallback` from DEBUG to TRACE-equivalent (drop unless `SET_ORCH_VERBOSE=1`).**
Even if the lookup is cheap, the log spam blinds the operator to real issues. The fallback is the *expected* path for non-lineage runs.

---

### Tier B — Land in week 2 (structural, medium risk)

**B1. Replace full replan with a Joiner-style scoped patch.**
Borrow LLMCompiler's pattern: when replan fires, the input to the planner is `(remaining_changes_dag, last_completed_change_summary, e2e_failures)` — and the output is a **plan patch** (`{add: [...], remove: [...], modify: [...]}`), not a full plan. The orchestrator applies the patch atomically; already-merged or in-flight changes are never re-emitted. Existing infrastructure (`enrich_plan_metadata` already strips `depends_on` to completed changes — extend that).

Expected impact: replan on a 24-change plan goes from "1 brief + 13 domain + 1 merge = 15 Claude calls" to "1 patch call ≈ 1 Claude call". 90 % token reduction on replans.

**B2. Decouple AMB resolution from replan.**
Today: AMB → re-digest → re-decompose → AMB still flagged → loop.
Proposed: AMB attaches to the affected change as `unresolved_ambiguities: [...]`. When that change's agent starts work, it gets a JIT clarification prompt (Sonnet, ≤2k tokens) that asks for resolution-or-defer. If resolved, scope is patched in-place. If deferred, change still proceeds with `[AMB:unresolved]` markers and a triage gate writes to `triage.md`.

Mirrors Magentic-One `max_reset_count` — caps the loop at 1 attempt per AMB instead of N. **Gap-analysis impact: zero** — AMBs are still recorded in `triage.md`; we just decouple the planner-side replan from the digest-side detection.

**B3. Phase 2 hardening: per-worker retry budget + partial-success policy.**
Wrap each `_decompose_single_domain` call in a `try/except + retry(max=2, backoff=exponential)`. On final failure, mark the domain as `decompose_failed: true` in the saved domain plan and surface to Phase 3's merge prompt as an explicit instruction ("domain X failed to decompose, re-emit minimal placeholder change"). Today the failure silently produces an empty domain; with this, the user sees a real error and the merge stage knows to compensate.

Add `max_workers` and `per_worker_timeout` to `orchestration.yaml::planner.parallel`. Default `max_workers=4` (down from 6) — Anthropic rate-limits favour smaller parallelism with fewer retries.

**B4. Phase 3 merge as map-reduce instead of one giant call.**
For domain_count > 8 OR total scope chars > 80 k, run a 2-level merge: pair-wise reduce (sonnet) → final merge (opus). Borrowed from `LLM × MapReduce` (arXiv 2410.09342). Each reduce step has its own Structured Information Protocol so gap-flags survive the merge. Smaller per-call context = lower OOM risk and faster.

**B5. Bound replan with a stall counter.**
Add `max_consecutive_replans_without_progress = 2` to directives. Track `replan_stall_count` in state — increment when a replan produces ≤1 net new change relative to the previous plan; reset on any merge. When the counter hits the cap, freeze the plan, surface a sentinel finding, and require human ack to continue. Magentic-One's `max_stall_count` analogue.

---

### Tier C — Land in weeks 3–4 (deeper, requires design)

**C1. Persistent digest with diff updates.**
Today digest is regenerated end-to-end. Switch to per-domain digest agents:
- Hash each spec section (master file + each child).
- Store `digest/<section-id>.json` with the section's input hash.
- On spec change, diff hashes; recompute only changed-section digests via per-section Claude calls.
- Reducer reads all `<section-id>.json` and produces `requirements.json`, `coverage.json`, `triage.md` deterministically.

Borrowed from GraphRAG (arXiv 2404.16130) and Cocoindex. **Gap-analysis impact: positive** — the reducer's job is to merge per-section gaps deterministically, so completeness is enforced by the data model rather than by the LLM remembering to include them.

**C2. Hierarchical retrieval at decompose time.**
Instead of injecting the entire `requirements.json` (50–80 reqs) into every Phase 2 domain prompt, retrieve the requirements tagged with the domain in question + cross-cutting requirements only. The full digest is still on disk and still feeds gap analysis; the planner just doesn't see the full thing per call. Reduces Phase 2 input ~3–5×.

**C3. Compress plan-scoped agent context every N iterations.**
SWE-bench finding: scheduled compression every 10–15 tool calls saved 22.7 % at no accuracy cost. The set-designer trace shows the agent's input_tokens (uncached) climbing on every retry — that's accumulated history. Add a sentinel-driven `/compact` analogue that fires when an agent's input_tokens exceed a threshold (e.g. 500 k uncached) without progress.

**C4. Switch Phase 1 brief and Phase 2 domain decompose default model from Sonnet to **Haiku** for specs with < 20 reqs.**
The brief is a simple aggregation; domain decompose with ≤6 reqs is straightforward. Reserve Sonnet+Opus for Phase 3 merge and the final plan. Estimated savings ~30 % on planner-side LLM cost for small specs (most consumer projects).

**C5. Event-driven post-merge replan.**
Even after B1, when a change merges we may want to replan the *immediately downstream* changes (their scope may shrink because their dependency is now done). Right now this is implicit in the next monitor poll. Make it explicit: emit `CHANGE_MERGED` event → if any pending change has the merged change in `depends_on`, kick a scoped Joiner call against just those. Single-writer, on the main loop — eliminates any temptation to put it in a thread.

---

## 4. Gap-analysis preservation — explicit guarantees

Every Tier B/C change is checked against this requirement:

| Change | Mechanism preserving completeness |
|---|---|
| B1 Joiner patch | Plan patch only mutates listed changes; nothing in `coverage.json`/`triage.md` is touched. The full digest still exists; planner just consumes a delta. |
| B2 JIT AMB | AMBs remain in `triage.md` (digest output). The decoupling is between *detection* (digest) and *replan trigger* (planner). Detection is unchanged. |
| B3 Phase 2 hardening | Failed-domain marker forces explicit handling instead of silent drop — strictly improves completeness. |
| B4 Map-reduce merge | Each reduce step carries forward the structured `gaps`/`unresolved` channel — same data, different sequencing. |
| C1 Diff-update digest | Reducer is deterministic and reads every section's gaps; output `coverage.json` is a strict union of inputs. |
| C2 Hierarchical retrieval | Full digest unchanged on disk; only the *prompt input* is filtered. Gap analysis is generated from the digest, not from the prompt. |

The single rule we will not break: **`coverage.json` and `triage.md` must reflect the full spec at all times**. They are produced by the digest; the digest is regenerated either fully (today) or per-section (C1). Either way they are complete by construction.

---

## 5. Rollout & validation

### Week 1 — Tier A
- A1 prompt-cache instrumentation behind `SET_ORCH_PLANNER_CACHE=1` (default off for one cycle).
- A2/A3/A4 inline.
- A5 trivial.
- **Validation**: re-run set-designer scaffold in `tests/e2e/scaffolds/set-designer/` (already present per untracked-files list) with cache on/off; compare `cache_read_tokens` and `cache_create_tokens` per LLM_CALL event. Target: ≥5× reduction on planner LLM calls.

### Week 2 — Tier B
- B1 behind `replan_strategy: scoped_patch` directive (default `full` until validated).
- B2 behind `amb_resolution: jit` directive.
- B3 always on (purely defensive).
- B4 behind `merge_strategy: map_reduce` (default `single` until validated).
- B5 always on (cheap).
- **Validation**: run the consumer-d scaffold (which exhibited the digest treadmill) and confirm:
  - Replan count ≤ stall cap.
  - No silent domain drops on injected fault.
  - `triage.md` and `coverage.json` byte-equivalent to today's output on a clean run (gap-analysis regression test).

### Weeks 3–4 — Tier C
- C1 + C2 land together (the retrieval depends on per-section hashing).
- C3 sentinel rule.
- C4 default-model change behind a cost-optimised preset.
- C5 event-driven replan.
- **Validation**: set-design-competitive-analysis spec (or larger) — confirm time-to-first-merge improves by ≥30 %, total planner-side tokens drop by ≥50 % vs current baseline.

### Acceptance criteria for shipping the whole programme

1. Planner-side input tokens (cache_read excluded) drop ≥60 % on a 13-domain spec.
2. Replan triggered by a single AMB fires ≤1 LLM call (vs 15 today).
3. Phase 2 ThreadPoolExecutor never produces a silent-empty domain on injected fault.
4. Phase 3 merge does not exceed 50 k input tokens per call (today: 80–120 k).
5. `coverage.json` and `triage.md` regression test passes on consumer-d, set-designer, micro-web scaffolds.
6. End-to-end: set-designer scaffold reaches at least 3 merged changes on a single SLA without manual replan.

---

## 6. Out of scope (deliberately)

- **Switching planner model from Anthropic** — set-core is built around Anthropic prompt caching semantics; no provider swap.
- **Sub-agent decompose** — Claude Code subagents cost ~7× more tokens (DEV blog citation). Phase 2 already uses parallelism; sub-agents would worsen it.
- **Eliminating the digest** — gap analysis is the digest's job; we are optimising *how* it runs, not removing it.
- **Manual replan only (disable auto)** — auto-replan is a feature; we are bounding it (B5), not removing it.

---

## 7. Open questions for design review

1. **A1 implementation order**: cache the digest-content section as 5-min ephemeral or 1-h ephemeral? 5-min is free if the planner+sentinel pings the cache within window; 1-h costs 2× write. The poll cycle is 15 s, so 5-min is the natural fit — but Phase 2 fanout to 13 parallel calls happens in seconds, so 1-h on the planner-rules section may be safer.
2. **B1 patch format**: JSON Patch (RFC 6902) vs custom delta format? JSON Patch is well-defined but verbose; custom is concise but bespoke. Lean toward custom with a strict validator.
3. **B4 map-reduce thresholds**: domain_count > 8 is a heuristic; should we tune by total token count instead?
4. **C1 per-section digest**: how do we identify "sections" in arbitrary spec markdown? Heading levels are the obvious answer but not all specs are well-structured. Possible answer: `set-spec-capture` already segments — reuse its segmentation.

---

## References

External research is in `/home/user/code2/set-core/docs/research/decompose-replan-optimization-2026-05-08-references.md` (companion file with sources).

Sources cited inline:

- Anthropic Prompt Caching docs — https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- LLMCompiler (arXiv 2312.04511) — Joiner / scoped replan
- ReWOO (arXiv 2305.18323) — planner/worker/solver decoupling
- LLM × MapReduce (arXiv 2410.09342) — Structured Information Protocol for gap-safe map-reduce
- GraphRAG community summaries (arXiv 2404.16130) — diff-update digest
- Magentic-One — `max_stall_count`, `max_reset_count` patterns
- Internal: `docs/research/token-optimization-analysis-2026-04-09.md` (agent-side cost analysis from craftbrew runs)
