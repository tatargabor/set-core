## Context

The planning pipeline (`lib/set_orch/planner.py`, `lib/set_orch/digest.py`, `lib/set_orch/templates.py`) drives all decomposition: spec → digest → planning brief (Phase 1) → parallel per-domain decompose (Phase 2) → merge (Phase 3) → plan. Replan re-enters the pipeline on AMB / e2e_failure / coverage_gap / spec_change / batch_complete triggers.

Three architectural facts shape the design:

1. **Anthropic prompt caching is structural, not a flag.** Cache breakpoints are placed inside the message blocks; the API decides hit-or-miss based on prefix-equivalence and TTL. Changing the order of any cached block invalidates everything after it. This forces a refactor of every prompt builder to return `list[ContentBlock]` rather than a single string.
2. **`coverage.json` and `triage.md` are the gap-analysis contract.** Anything we do to optimize tokens or replans must keep these byte-equivalent on a clean run. They are produced by the digest reducer; the planner consumes them but does not author them.
3. **The orchestrator's monitor loop is single-threaded by design** (engine.py:1121 `Monitor loop started`). The only threading is `ThreadPoolExecutor` inside `_phase2_parallel_decompose`. We will not add new threads — when scoped replan needs to fire on a merge event, it runs on the main loop with the merge handler.

Constraints:

- All new behavior is gated by directives (`replan_strategy`, `amb_resolution`, `merge_strategy`, `planner.parallel.*`) so existing runs are unchanged until operators opt in.
- The on-disk content-addressed digest cache (`~/.cache/set-orch/digest-cache/`) is reused as the storage layer for diff-update digest sections. We do not introduce a new cache directory.
- The `domains-plans-<lineage-id>.json` file (already used for selective replan) is reused as the input for scoped patches.
- We must not change the consumer-facing schema of `orchestration-plan.json` except by additive fields.

## Goals / Non-Goals

**Goals**

- Drop planner-side input tokens (cache_read excluded) ≥60 % on a 13-domain spec.
- Reduce AMB-triggered replans to ≤1 LLM call (vs ~15 today).
- Eliminate silent empty-domain plans from Phase 2 fan-out.
- Keep `coverage.json` and `triage.md` byte-equivalent across the whole programme on a clean run.
- Bound runaway replan loops with a stall counter.
- Make optimization opt-in tier by tier so each tier ships independently.

**Non-Goals**

- Provider swap (Anthropic-only).
- Sub-agent decompose inside the planner (~7× cost per published research).
- Removing the digest or AMB detection (gap analysis must stay).
- Disabling auto-replan entirely (operators rely on it for long-running specs).
- Changing the on-disk schema of `orchestration-plan.json` except by additive fields.

## Decisions

### D0. Serial-by-default decompose strategy

The single biggest framing decision. Empirically, the 3-phase domain-parallel pipeline:

- Costs $25–41 per session in observed multi-domain runs (planner-side `LLM_CALL` events).
- Re-runs the whole P1+P2+P3 pipeline 3–5 times per session because every replan/retry restarts from scratch.
- Produces simultaneous-burst failures (5–6 workers fail within 1 s) when the LLM-side rate limit cascades.
- Hits hard 1800 s timeouts on Phase 3 merge for the largest specs.

Meanwhile a single-call decompose (the existing flat path at `planner.py:2674-2693`, used today only as a fallback) succeeded in the same sessions in 992 s for $2.17 with 497 k of cache_read tokens (heavy in-call tool reuse). The model handles 13 domains in one shot fine, and Anthropic's prompt cache makes subsequent tool turns within the call effectively free.

Decision: **serial single-call becomes the primary path.** The 3-phase pipeline is preserved for very large specs that exceed the single-call context budget, gated by an explicit token estimate.

Mechanism (capability `planner-strategy-routing`):

- New directive `planner.strategy: serial | parallel | auto`, default `auto`.
- `auto` invokes `estimate_flat_prompt_tokens(digest_dir, replan_ctx)` (a pure-Python file-size sum divided by 3.5 chars/token) and picks `serial` if the estimate ≤ 120 000 tokens, else `parallel`.
- The legacy `DOMAIN_PARALLEL_MIN_REQS = 30` heuristic at `planner.py:2630` is removed — req_count alone never forces parallel.
- Operator override via the directive forces a path regardless of size.

**Why 120 k:** Opus context window is 200 k. Phase 3 merge at full 13-domain load already hits ~80 k input. A single-call flat prompt at 120 k input leaves ~80 k for output + tool-use turns. We tune empirically in Tier A validation.

**Alternative considered:** keep parallel as default with caching. Rejected — caching helps Phase 2 fan-out modestly, but the dominant cost is *retries*, not single-call size, and the parallel path's failure surface is 15 LLM calls vs serial's 1.

**Alternative considered:** remove the parallel path entirely. Rejected — for specs that exceed the context budget (≥25 domains, ≥250 reqs), single-call would truncate. We keep parallel as the rare-but-real fallback and harden it (D4, D5, D11).

### D1. Layered prompt caching with 4 breakpoints

Every planner-side prompt becomes `list[ContentBlock]` with breakpoints placed at:

```
BP1 (1h TTL): tools schema + JSON output skeleton          ← rarely changes
BP2 (1h TTL): system role + _PLANNING_RULES_CORE + project conventions
BP3 (5m TTL): digest stable section (requirements.json, conventions.json, domains/*.md)
BP4 (uncached): spec tail / replan delta / cycle-volatile context
```

Phase 2 fan-out specifically: BP1+BP2 are identical across all parallel domain calls and will hit cache; BP3 differs per domain (different domain summary). With 13 domains we expect 12× cache hits on BP1+BP2 ≈ 100 k tokens × 12 ≈ 1.2 M tokens served from cache.

**Alternative considered:** single 1h breakpoint at the bottom of system. Rejected — the Phase 2 prompt has per-domain content in its middle (`### Domain: <name>`), and a single breakpoint forces the entire prefix to be re-cached for each domain. Layering separates the per-domain volatile section.

**Alternative considered:** rely on Anthropic's automatic prefix caching without explicit `cache_control`. Rejected. Empirically, the SDK's auto cache provides ~13 k baseline `cache_read` per call (the tools/system prefix) plus occasional in-call hits, but cross-worker sharing in a Phase 2 fan-out almost never lands because parallel staggering pushes later workers past the default 5-min TTL. Explicit 1-h breakpoints make cross-call sharing reliable; without them we leave 80 % of the potential cache benefit on the table.

### D2. Scoped replan patches (Joiner-style)

Instead of re-emitting the whole plan, the replanner emits a JSON patch:

```json
{
  "patch_version": 1,
  "base_plan_version": 7,
  "operations": [
    {"op": "add", "change": {...}},
    {"op": "remove", "name": "obsolete-change"},
    {"op": "modify", "name": "auth-foundation", "fields": {"scope": "..."}}
  ],
  "reasoning": "..."
}
```

The orchestrator applies the patch atomically inside the main loop:

1. Validate patch (no removal of merged/in-flight changes; no add with duplicate name; no modify of completed change).
2. Acquire state lock.
3. Apply operations sequentially.
4. Increment `plan_version`.
5. Persist; release lock.
6. Emit `PLAN_PATCHED` event.

If validation fails, the patch is rejected and the orchestrator falls back to the full-replan code path (today's behavior). The fallback is observable so we can tune the patch generator.

**Alternative considered:** RFC 6902 JSON Patch. Rejected — JSON Patch operates on JSON pointers and would force the planner to compute paths like `/changes/3/scope`. Our object identity is the change `name`, which is human-readable and stable across replans. A custom patch with named operations is easier to write and easier to review.

**Alternative considered:** full plan with a server-side diff. Rejected — the LLM is the source of truth for which changes need updating; making it produce the full plan defeats the purpose. Token cost was the primary objection.

### D3. JIT ambiguity resolution

AMBs detected during digest still land in `triage.md` (gap-analysis source of truth, unchanged). AMBs marked `resolution: "deferred"` or with no resolution are no longer injected into the planner prompt. Instead they attach to the affected change(s) via `unresolved_ambiguities: ["AMB-001", ...]`.

When the change's implementing agent starts work, the dispatcher injects a JIT clarification prompt (Sonnet, ≤2 k tokens) that asks the agent to either resolve the ambiguity (returning `resolution_note`) or escalate it (`resolution: "human"`). The result is patched into the change's scope and journalled. AMB resolution is observable per-change rather than spec-wide.

**Why this preserves gap analysis:** `triage.md` is unchanged. We are decoupling the *trigger* (AMB found) from the *response* (full replan vs JIT clarification). `coverage.json` is unaffected because requirement-to-change mapping is independent of AMB resolution.

**Alternative considered:** resolve AMBs in a dedicated planner pre-pass. Rejected — that's still a global step that runs before any change is dispatched. JIT scopes the resolution to the agents that actually need it.

### D4. Phase 2 hardening (parallel path only)

This decision applies only when `planner.strategy` resolves to `parallel`. With serial as the default, most projects never hit this path; the hardening is tail-risk insurance for the rare large-spec case.

Per-worker retry budget (`max=2`, exponential backoff). On final failure:

```python
domain_plans[domain] = {
  "decompose_failed": True,
  "error": str(exc),
  "fallback_changes": []   # empty
}
```

Phase 3 merge prompt receives this explicitly: "Domain X failed to decompose (reason: timeout). Re-emit a single placeholder change with scope='[REDECOMPOSE_NEEDED] domain X' so coverage gap is visible." A subsequent replan cycle picks it up.

`max_workers` defaults to 4 (down from 6 = `min(domains, 6)`). Per-worker timeout default 300 s (today: no timeout).

**Why we don't drop the domain silently:** that is the current behaviour and the source of the instability. Making the failure visible at the plan level forces the operator (or the next replan) to address it, and prevents `coverage.json` from claiming false coverage.

### D5. Phase 3 map-reduce when large (parallel path only)

Active only on the parallel path. Heuristic: domain_count > 8 OR `sum(len(json.dumps(plan)) for plan in domain_plans.values()) > 80_000` chars triggers map-reduce.

Reduce stage: pair-wise merge of domain plans (Sonnet, parallel, 2 calls in flight max). Each reduce call's output is a partial merged plan with explicit `gaps[]` channel — the Structured Information Protocol from `arXiv 2410.09342`. Final stage: synthesizer (Opus) merges the reduced halves with full context including all gaps.

Each reduce step output schema:

```json
{
  "merged_changes": [...],
  "gaps": [{"requirement_id": "REQ-001", "reason": "no domain claimed"}],
  "conflicts": [{"name": "auth-foundation", "duplicated_in": ["domain-a", "domain-b"]}]
}
```

Synthesizer must address every gap. Gap-analysis preservation by data-model construction.

**Alternative considered:** chunked merge with a shared scratch document. Rejected — coordination across calls is fragile; pair-wise reduce is well-studied and produces deterministic ordering.

### D6. Stall counter

New state field: `replan_stall_count: int` (default 0). After each replan:

- If patch had `len(operations) > 1` AND at least one `add`: reset to 0.
- Otherwise: increment.

When `replan_stall_count >= max_consecutive_replans_without_progress` (default 2):

- Status → `replan_stalled`.
- Sentinel finding logged (`type=REPLAN_STALL`, severity=warning).
- Replan loop pauses; operator must POST `/api/<project>/orchestration/ack-stall` to resume.

Reset on any `CHANGE_MERGED` event.

**Alternative considered:** absolute replan count cap. Rejected — long specs legitimately replan many times. The stall counter only fires when replans are *unproductive*, which is the failure mode we're targeting.

### D7. Diff-update digest

The digest is decomposed into per-section units. A "section" is identified by:

1. `set-spec-capture` segmentation if available (already produces section IDs).
2. Otherwise, top-level markdown headings (#, ##) with stable kebab-case IDs.
3. Cross-document references stay flat.

Each section's content is hashed (sha256 of normalized text). On digest run:

- For each section: if `digest/sections/<section-id>.json` exists with matching hash, reuse.
- Otherwise: per-section Claude call (Sonnet) producing `{requirements, ambiguities, coverage_hints, gaps}`.
- Reducer (deterministic Python, no LLM): merge all sections into `requirements.json`, `coverage.json`, `triage.md`.

The reducer is deterministic so `triage.md` byte-equivalence is verifiable in tests.

**Why the reducer is deterministic Python and not an LLM call:** if the reducer were an LLM, it could drop gaps (the very failure mode `arXiv 2410.09342` warns about). With a Python reducer over typed per-section outputs, gap inclusion is guaranteed by code.

**Alternative considered:** LLM reducer. Rejected — gap-analysis preservation requires deterministic merge.

### D8. Hierarchical retrieval at decompose time

For Phase 2 domain prompts: instead of full `requirements.json`, send only:

- Requirements tagged with the domain.
- Cross-cutting requirements (those whose `also_affects_domains` includes the domain).
- A summary line for each other-domain requirement (so the planner sees the shape but not the detail).

The full digest stays on disk. Coverage analysis (which is whole-digest) runs on the digest, not on the prompt.

### D9. Event-driven post-merge scoped replan

On `CHANGE_MERGED`:

- Identify pending changes that have the merged change in `depends_on` ("downstream").
- If any downstream changes exist AND the merged change's scope substantially differs from its declared scope (e.g., agent added unexpected dependencies), kick a scoped patch call against just those downstream changes.
- Always runs on the main loop (no thread).

Defaults to off until D2 (scoped patch) ships.

### D10. Domain plan reuse on replan

Capability `replan-domain-plan-reuse`. The observed retry storm (3 full P1+P2+P3 pipelines in session A, 5 in session B) happens because every replan/retry restarts from scratch. Today's `_save_domain_plans` writes `domains-plans-<lineage>.json` but the lookup path uses `LineagePaths.plan_domains_file` which falls back to a non-lineage path on every poll cycle (the source of the 53× `LineagePaths fallback` log lines), so the saved file is rarely found.

Mechanism:

- After Phase 2, persist a per-domain input hash (`sha256(domain_summary || requirements_json || brief_json || conventions)`) alongside the saved domain plans.
- On replan, load the saved file; for each domain in the new digest, recompute the input hash and compare. Hash match → reuse the saved domain plan. Hash mismatch → re-decompose only that domain.
- Brief change invalidates all domains (because brief is part of the hash).
- Telemetry: emit `REPLAN_REUSE` event with `{reused: N, redecomposed: M, total: T}` so we can measure cache effectiveness post-run.

For the serial path, the analogue is whole-plan reuse: when the digest input hash matches the prior decompose's input hash AND `replan_ctx.completed` is empty, skip the Claude call entirely and return the prior plan. (When `completed` is non-empty the planner needs to advance to the next phase, so the call must run.)

**Alternative considered:** content-addressed cache shared across projects (the existing `~/.cache/set-orch/digest-cache/` model). Rejected — domain plans contain project-specific scope text (file paths, change names) and aren't safely sharable. Per-project storage at the existing `domains-plans-<lineage>.json` location is correct.

### D11. Burst-failure mitigation in Phase 2 (parallel path only)

Empirically, when the LLM rate-limits, all in-flight Phase 2 workers fail within a 1 s window (observed: 6 simultaneous failures at 22:58:15 in both sessions). Today this triggers per-worker retries that all fire simultaneously and re-trip the rate limit.

Mechanism:

- Track per-worker failure timestamps in `_phase2_parallel_decompose`.
- When ≥3 workers fail within a 5 s window, pause new dispatches for `parallel.rate_limit_backoff` seconds (default 30) before any retry.
- During the pause, the executor reports `burst_backoff_active` in logs at WARNING level so operators can correlate with API rate-limit events.
- After the pause, retries resume with the existing per-worker backoff schedule.

This is a coarse circuit-breaker, not a per-call rate limiter. Its job is to prevent the retry storm from amplifying a transient rate-limit hiccup into 6 cascading failures.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Cache invalidation cascade — changing one breakpoint blows away caching for everything after it. | Layer order is fixed and codified in `templates.py` constants; reviewers must understand cascade. CI test asserts breakpoint ordering on every render call. |
| Scoped patch produces invalid mutations (e.g., remove of a merged change). | Patch validator rejects invalid ops; orchestrator falls back to full replan; metric `patch_rejection_rate` surfaced. |
| JIT AMB resolution gives different answers per change (same AMB resolved differently in two changes). | AMB resolution is journalled per-change and the final scope captures the resolution. Inconsistencies surface in code review (the integrating gate). |
| Phase 2 explicit-failure marker breaks downstream tooling expecting empty-domain = "no work needed". | We grep `lib/set_orch/` for callers of `domain_plans[domain]` first; today no consumer relies on the empty-vs-failed distinction. Tooling change is contained to the merge prompt. |
| Map-reduce merge introduces non-determinism via pair ordering. | Pair ordering is deterministic (sort by domain name). Reducer prompts are seeded. |
| Stall counter halts orchestration unexpectedly. | Default off (`max_consecutive_replans_without_progress = 0`); operators opt in. Sentinel finding makes the cause discoverable. |
| Diff-update digest and full digest produce different `triage.md` due to LLM non-determinism per section. | Reducer is deterministic Python; per-section LLM calls have stable seeds; CI gap-analysis regression test catches drift on a fixed corpus. |
| Hierarchical retrieval drops a requirement the planner would have considered cross-cutting. | Cross-cutting requirements are explicitly included via `also_affects_domains`; coverage of the test scaffold validates no requirement is dropped. |
| Event-driven post-merge replan races with the main monitor loop. | Runs on the main loop, not in a thread; merge handler explicitly invokes the scoped replan synchronously before releasing the merge queue lock. |
| Tier rollout creates intermediate states with mixed defaults. | Each tier's directives are independent; defaults are `safe / today's behavior` until validated. Acceptance criteria for the whole programme require all tiers integrated; intermediate states are fine. |

## Migration Plan

### Phase 1 — Tier A (week 1, always-on)

1. Refactor every `render_*_prompt` and `_DIGEST_PROMPT_TEMPLATE` to return `list[ContentBlock]`.
2. Update `subprocess_utils.run_claude` (and any caller that builds the SDK request) to accept blocks and pass through `cache_control`.
3. Memoize `LineagePaths` per poll cycle.
4. Add `lineage-index.json` with incremental updates.
5. Move memory hygiene off the poll path.
6. Demote fallback log line.

Validation: cache hit/miss counted in LLM_CALL events. Token regression test passes. No behavior change.

### Phase 2 — Tier B (week 2, opt-in)

1. Implement scoped patch path (`_replan_scoped_patch_cycle`) alongside the existing `_auto_replan_cycle`.
2. Add directive `replan_strategy: scoped_patch | full` (default `full`).
3. Implement JIT AMB resolution path; add directive `amb_resolution: jit | inline` (default `inline`).
4. Phase 2 hardening always-on (defensive change, no flag).
5. Map-reduce merge implementation; directive `merge_strategy: single | map_reduce` (default `single`).
6. Stall counter implementation; directive `max_consecutive_replans_without_progress` (default 0 = off).

Validation: directive-flipped runs on test scaffolds, gap-analysis regression test on a fixed spec.

### Phase 3 — Tier C (weeks 3–4, opt-in)

1. Section-hashing and per-section storage.
2. Deterministic reducer.
3. Hierarchical retrieval into Phase 2 prompts.
4. Compression sentinel rule.
5. Cost-optimized model preset extension.
6. Event-driven post-merge replan.

Validation: large-spec scaffold time-to-first-merge improvement ≥30 %, planner-side token reduction ≥50 %.

### Rollback

Each tier's changes are independently reversible:
- Tier A: revert `templates.py` block-list refactor (keeps callers working with single string).
- Tier B: directive defaults (`replan_strategy: full`, `amb_resolution: inline`, `merge_strategy: single`) restore today's behavior without code revert.
- Tier C: feature-flagged similarly.

## Open Questions

1. **Cache TTL for digest section.** 5-min ephemeral is free if planner+sentinel pings it within window; 1-h costs 2× write. Phase 2 fan-out completes in seconds, so 1-h on planner-rules section is safer; 5-min on digest is the natural fit. Validation: measure cache hit rates on first runs.
2. **Scoped patch format.** Custom named-op format (D2) vs RFC 6902 JSON Patch. Custom is chosen here; revisit if integration with external tools wants standard JSON Patch.
3. **Section identification.** Heading levels are not always reliable in arbitrary spec markdown. Falling back to `set-spec-capture` segmentation when present; need a fallback for specs not produced by it.
4. **Map-reduce thresholds.** `domain_count > 8` is a heuristic; total token count may be a better predictor. Empirical tuning during Tier B validation.
5. **Stall counter default.** Should it default to `2` after Tier B validates, or remain `0` (off) and operators opt in? Conservative default: `0` until at least 3 multi-domain runs validate without false positives.
