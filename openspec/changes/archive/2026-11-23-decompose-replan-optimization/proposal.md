> **Superseded 2026-11-23 — closed without implementing the open tasks.** This change extends the
> orchestration engine (E2E gates, decompose/planner, fix-iss, the web project template and the
> run dashboards), which `fleet-era-consolidation` retires (stages 4-5: `retire-orchestration-cli`,
> `retire-orchestration-engine`). Archived with `--skip-specs` semantics: no delta reached
> `openspec/specs/`. Tasks ticked here were shipped; unticked ones were not.

## Why

Two recent multi-domain orchestration sessions show the planning pipeline burning ~$25–41 of LLM budget per session before any change merges. Telemetry from `~/.local/share/set-core/runtime/<project>/orchestration/events.jsonl` (`LLM_CALL` events with `purpose` ∈ {`digest`, `decompose`, `decompose_brief`, `decompose_domain`, `decompose_merge`}):

| Session | Phase 1 calls | Phase 2 calls | Phase 3 calls | Phase 2 failures | Total $ |
|---|---:|---:|---:|---:|---:|
| Multi-domain session A (~13 domains, 49 reqs) | 3 | 57 | 1 | 8 | $25.00 |
| Multi-domain session B (~13 domains, 30–76 reqs) | 6 | 53 | 3 (1 timed out at 1800 s) | 7 | $41.24 |

Five structural problems explain the cost:

1. **The 3-phase pipeline (brief → parallel domain decompose → merge) is the default path for any spec with ≥30 reqs** (`DOMAIN_PARALLEL_MIN_REQS` at `planner.py:2630`). For typical specs the model handles a single-call decompose fine, observed: one flat call succeeded in 992 s for $2.17 with `cache_read = 497,494` (heavy in-call tool reuse from cache). The 3-phase path is paying for theoretical parallelism that mostly produces retry storms.
2. **No `cache_control` directives anywhere** in `templates.py` planner/digest prompts (`grep cache_control lib/set_orch/templates.py` → 0). Anthropic's automatic SDK cache provides ~13k baseline `cache_read` per call (tools prefix) but cross-worker sharing in Phase 2 fan-out rarely lands because parallel staggering pushes later workers past the default 5-min TTL. Explicit 1-h breakpoints make sharing reliable.
3. **Replan and ambiguity (AMB) resolution are coupled to a full re-decompose** — one ambiguity triggers a full P1 + N domain calls + P3 merge (≈15 LLM calls) even when only one change scope is affected. Replans also restart from scratch instead of reusing already-saved domain plans (the `LineagePaths fallback` log line shows `domains-plans-<lineage>.json` lookups missing the lineage-suffixed path on every cycle).
4. **Phase 2 `ThreadPoolExecutor`** in `_phase2_parallel_decompose` has no per-worker retry, no per-worker timeout knob, and silently produces empty-domain plans on failure. Both sessions show simultaneous-burst failures (5–6 workers fail within 1 s of each other — the rate-limit cascade pattern).
5. **Phase 3 merge has a hard 1800 s timeout** with no configurability and no checkpointing. Session B hit it.

Full diagnosis (logs, token counts, code locations) is in `docs/research/decompose-replan-optimization-2026-05-08.md`.

## What Changes

### Tier A — strategy flip + caching + noise reduction (week 1, low risk)

- **Flip planner default to single-call (serial) decompose.** New directive `planner.strategy: serial | parallel | auto` with default `auto`. The `auto` branch estimates the assembled flat-prompt input tokens and picks `serial` when ≤ `SINGLE_CALL_MAX_INPUT_TOKENS` (default 120 000) else `parallel`. The legacy `DOMAIN_PARALLEL_MIN_REQS = 30` heuristic is removed. Operator can force either strategy via the directive.
- **Reuse saved domain plans on replan.** `_save_domain_plans` already writes `domains-plans-<lineage>.json`; on replan, `_auto_replan_cycle` SHALL look it up via `LineagePaths.plan_domains_file`, hash each domain's input (digest summary + requirements + brief), and reuse cached domain plans whose hash matches. Eliminates the observed P1+P2+P3-from-scratch-on-every-replan storm (3 full pipelines in session A, 5 in session B).
- Add layered Anthropic prompt caching (4 breakpoints: tools / system+rules / digest-stable / spec-tail) to `render_planning_prompt`, `render_brief_prompt`, `render_domain_decompose_prompt`, `render_merge_prompt`, and `_DIGEST_PROMPT_TEMPLATE`. Refactor each to return `list[ContentBlock]` instead of a single string and emit `cache_control: {"type": "ephemeral", "ttl": "1h" | "5m"}` per layer.
- Memoize `LineagePaths.{plan_path, plan_domains_file, digest_dir}` per poll cycle; demote the `LineagePaths fallback` log line to TRACE-equivalent.
- Build a `set/orchestration/lineage-index.json` so `compute_phase_offset` is O(1) instead of a sequential JSONL scan.

### Tier B — structural (week 2, medium risk)

- **Scoped replan patches**: when replan fires, the planner emits a `{add, remove, modify}` patch against the current plan instead of regenerating it. Already-merged or in-flight changes are never re-emitted. New directive: `replan_strategy: scoped_patch | full` (default `scoped_patch` after validation).
- **JIT ambiguity resolution**: AMBs attach to the affected change as `unresolved_ambiguities`; resolved by the change's implementing agent at start-of-work via a small Sonnet/Haiku call. Decoupled from replan triggers. AMBs still recorded in `triage.md` (gap analysis preserved). New directive: `amb_resolution: jit | inline`.
- **Replan stall counter**: `max_consecutive_replans_without_progress = 2`. When tripped, freeze the plan, surface a sentinel finding, require human ack. Magentic-One `max_stall_count` analogue.

### Tier B (parallel-path only — active only when `planner.strategy` resolves to `parallel`)

- **Phase 2 hardening**: per-worker retry budget (`max=2`, exponential backoff) and explicit `decompose_failed: true` marker on terminal failure (replaces today's silent empty-domain output). Configurable `planner.parallel.max_workers` and `per_worker_timeout`.
- **Phase 2 burst-failure mitigation**: when ≥3 in-flight workers fail within a 5 s window, the executor SHALL pause new dispatches for `parallel.rate_limit_backoff` seconds (default 30) before retrying. Address the observed simultaneous-burst pattern (5–6 workers fail within 1 s).
- **Phase 3 configurable timeout**: directive `planner.parallel.merge_timeout` (default 1500 s, was hardcoded 1800 s). When a Phase 3 call exceeds 600 s, log a WARNING with elapsed-time + token-budget snapshot.
- **Phase 3 map-reduce merge**: when domain_count > 8 OR total scope > 80 k chars, run pair-wise reduce (Sonnet) then final merge (Opus). Borrowed from arXiv 2410.09342's Structured Information Protocol so gap-flags survive. New directive: `merge_strategy: single | map_reduce`.

### Tier C — deeper (weeks 3–4)

- **Diff-update digest**: per-section content hashing; recompute only changed-section digests on spec edit. Reducer merges per-section outputs into `requirements.json` / `coverage.json` / `triage.md` deterministically. GraphRAG / Cocoindex pattern.
- **Hierarchical retrieval at decompose time**: Phase 2 domain prompts receive only domain-tagged + cross-cutting requirements (not the full `requirements.json`). The full digest stays on disk; gap analysis is unchanged.
- **Scheduled context compression** for long-running agents (every 10–15 supervisor cycles when `input_tokens` exceeds threshold without progress). SWE-bench finding: ~22.7 % saving at no accuracy cost.
- **Cost-optimized model preset** that selects Haiku for Phase 1 brief and Phase 2 domains when `requirement_count < 20`. Reserves Opus for merge and final plan.
- **Event-driven post-merge scoped replan**: emit `CHANGE_MERGED` event, kick a Joiner call against direct downstream changes only. Single-writer on the main loop.

### Acceptance criteria for the whole programme

1. **Strategy default**: a fresh decompose on a ≤80-req digest takes the `serial` path; a >180-req digest takes `parallel`. The `auto` decision is deterministic given the same digest input.
2. **Cost on retry-storm scenario**: a 13-domain digest re-decomposed 3 times (mirroring the observed P1+P2+P3-3× pattern) costs ≤$5 total planner-side (vs $25–41 today). Measured from `LLM_CALL` event `cost_usd` field.
3. **Planner-side input tokens** (cache_read excluded) drop ≥60 % on a 13-domain spec.
4. AMB-triggered replan fires ≤1 LLM call (vs ~15 today).
5. **Replan reuse**: when a replan fires after one merge on a 13-domain plan, ≤2 per-domain Claude calls run (only the affected domain plus cross-cutting), not all 13.
6. Phase 2 fan-out never produces a silent-empty domain on injected fault. **(Parallel path only.)**
7. Phase 3 merge does not exceed 50 k input tokens per call. **(Parallel path only — no Phase 3 in serial mode.)**
8. `coverage.json` and `triage.md` are byte-equivalent to today's output on a clean run (gap-analysis regression test).
9. End-to-end: a multi-domain test scaffold reaches ≥3 merged changes on a single SLA without manual replan.

### Out of scope

Provider swap; Claude Code subagents inside the planner (~7× cost); removing the digest; disabling auto-replan entirely.

## Capabilities

### New Capabilities

- `planner-strategy-routing`: directive-driven selection between single-call (serial) and 3-phase (parallel) decompose paths with an `auto` mode that estimates the assembled flat-prompt input tokens and picks a path. Defines `planner.strategy` directive, `SINGLE_CALL_MAX_INPUT_TOKENS` threshold, the `estimate_flat_prompt_tokens` function contract, and removal of the legacy `DOMAIN_PARALLEL_MIN_REQS` heuristic.
- `planner-prompt-caching`: declared layered cache breakpoints (tools / system+rules / digest / spec-tail) on every planner-side Claude call (`render_planning_prompt`, `render_brief_prompt`, `render_domain_decompose_prompt`, `render_merge_prompt`, `_DIGEST_PROMPT_TEMPLATE`). Defines breakpoint placement rules, TTL per layer, and the `ContentBlock`-list return contract.
- `replan-scoped-patch`: Joiner-style scoped replan — planner consumes `(remaining_changes_dag, last_completed_summary, e2e_failures)` and emits a `{add, remove, modify}` plan patch instead of a full plan. Includes patch schema, atomic application semantics, and the stall counter.
- `replan-domain-plan-reuse`: on replan, look up the saved `domains-plans-<lineage>.json`, hash each domain's input (digest summary + requirements + brief), reuse cached domain plans whose hash matches. Eliminates the observed 3–5× P1+P2+P3 pipeline-from-scratch retry storm.
- `amb-jit-resolution`: ambiguities attach to changes as `unresolved_ambiguities` and are resolved JIT by the implementing agent (cheaper model). Decouples digest-side AMB detection from planner-side replan triggers; preserves `triage.md` as the gap-analysis source of truth.
- `digest-diff-update`: per-section content-hashed digest. On spec edit, recompute only changed-section digests; deterministic reducer merges per-section outputs into `requirements.json`, `coverage.json`, `triage.md`. Defines section identification rules and the reducer contract.

### Modified Capabilities

- `orch-plan-python`: serial-by-default routing; Phase 2 per-worker retry budget + explicit `decompose_failed` marker; burst-failure mitigation; configurable `max_workers` / `per_worker_timeout` / `merge_timeout`; Phase 3 map-reduce path; hierarchical retrieval into Phase 2 prompts.
- `orch-replan-python`: stall counter (`max_consecutive_replans_without_progress`); integration with `replan-scoped-patch` and `replan-domain-plan-reuse`; event-driven post-merge scoped replan trigger.
- `orch-digest-python`: integration with `digest-diff-update` (the existing on-disk content-addressed cache becomes the per-section storage layer); decoupling from AMB-driven replan.

## Impact

### Code

- `lib/set_orch/templates.py` — every `render_*_prompt` function refactored to return `list[ContentBlock]`; `_DIGEST_PROMPT_TEMPLATE` likewise. Callers (`planner.py`, `digest.py`, `subprocess_utils.py:run_claude`) updated to pass blocks through to the Anthropic SDK.
- `lib/set_orch/planner.py` — strategy router (`run_planning_pipeline` selects serial vs parallel based on `planner.strategy` directive and `estimate_flat_prompt_tokens`); `_phase2_parallel_decompose` per-worker try/retry/marker + burst-failure backoff (parallel path); `_phase3_merge_plans` map-reduce branch (parallel path); `run_planning_pipeline` mode selection for scoped patch vs full; new patch parser/validator; domain-plan reuse on replan.
- `lib/set_orch/digest.py` — per-section hashing + reducer; on-disk layout `digest/sections/<section-id>.json`; reducer that produces today's outputs.
- `lib/set_orch/engine.py` — `_handle_auto_replan` / `_auto_replan_cycle` integration with scoped patch; stall counter state field; `CHANGE_MERGED` event emitter; AMB-resolution removed from replan triggers.
- `lib/set_orch/paths.py` — memoize `LineagePaths`; demote fallback log line.
- `lib/set_orch/state.py` — new fields: `replan_stall_count`, `unresolved_ambiguities` (per-change).
- `lib/set_orch/config.py` — directives: `planner.strategy` (serial|parallel|auto, default auto), `replan_strategy`, `amb_resolution`, `merge_strategy`, `planner.parallel.max_workers`, `per_worker_timeout`, `merge_timeout`, `rate_limit_backoff`, `max_consecutive_replans_without_progress`.
- `lib/set_orch/model_config.py` — cost-optimized preset extension for Haiku-on-small-spec.
<!-- mcp-server memory hygiene improvements are adjacent to planner work and tracked in a separate change. -->


### Behavior

- Planner LLM calls become much cheaper but observable per-LLM_CALL `cache_create_tokens` will rise on cold runs (write-cost) and `cache_read_tokens` will dominate on warm runs.
- Replan failure modes change: a transient AMB no longer triggers a 15-call replan storm; instead it attaches to the affected change.
- Phase 2 explicit-failure surface: failed domains will produce a visible `decompose_failed: true` in `orchestration-plan.json` instead of silent empties.
- Stall counter introduces a new terminal state for runaway replans — operators must ack to continue.

### Migration

- The strategy flip (`planner.strategy: auto` default = serial for typical specs) **changes the default code path** for ≤80-req digests. Existing parallel-path behaviour remains accessible via `planner.strategy: parallel` directive override.
- Tier B behavior is feature-flagged via directives with safe defaults (`replan_strategy: full`, `amb_resolution: inline`, `merge_strategy: single`) so existing runs are unaffected until the operator opts in.
- The diff-update digest writes to a new `digest/sections/` subtree alongside today's outputs — the consumer reads `requirements.json` etc. unchanged. Migration is one rebuild.
- Tier A items (strategy flip, replan reuse, cache directives, memoization, log demote) are always-on; their effect is observable token cost but no functional regression on a clean run.

### Tests / validation

- Tier A strategy & caching: planner-pipeline scaffold under `tests/e2e/scaffolds/`. Verify (a) `auto` resolves to `serial` for ≤80-req digest and `parallel` for >180-req digest; (b) explicit `parallel` runs the 3-phase path; (c) ≥5× input-token reduction on planner LLM calls with cache directives on (measured from `LLM_CALL` token fields).
- Tier A reuse: digest-treadmill scaffold — replicate the multi-cycle retry pattern from real sessions. Inject a single-domain change between cycles; assert only the affected domain re-runs Phase 2 on the second cycle, not all 13.
- Tier B Phase 2 hardening (parallel path): force `planner.strategy: parallel`, inject a Phase 2 worker fault, assert no silent empty-domain plan and `decompose_failed` marker present.
- Tier B burst-failure: inject 3 simultaneous worker errors, assert backoff fires and recovery succeeds.
- Tier C: large-spec scaffold (≥20 domains, ≥150 requirements). Assert time-to-first-merge ≥30 % improvement and planner-side tokens ≥50 % reduction vs current baseline.
- Gap-analysis regression test: deterministic byte-comparison of `coverage.json` + `triage.md` before/after each tier on the same spec.

### Dependencies

- Anthropic SDK supports `cache_control` (already in use elsewhere); no new dependency.
- Existing `~/.cache/set-orch/digest-cache/` infrastructure is reused for per-section storage.
- Existing `domains-plans-<lineage-id>.json` infrastructure (already used for selective replan) is reused for scoped-patch input assembly.
