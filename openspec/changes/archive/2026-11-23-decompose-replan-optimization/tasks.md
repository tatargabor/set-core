## 0. Tier A — Strategy routing (serial-by-default)

- [x] 0.1 Add directive `planner.strategy: serial | parallel | auto` (default `auto`) and `planner.single_call_max_input_tokens` (default 120000) to `lib/set_orch/config.py` with precedence orchestration.yaml > state.extras.directives > env `SET_ORCH_PLANNER_STRATEGY` [REQ: planner-strategy-directive]
- [x] 0.2 Implement `estimate_flat_prompt_tokens(digest_dir, replan_ctx)` in `lib/set_orch/planner.py` as pure-Python file-size sum / 3.5, with graceful handling of missing files [REQ: token-estimator-does-not-invoke-claude]
- [x] 0.3 Implement auto-decision rule in `run_planning_pipeline()`: serial when estimate ≤ threshold, parallel otherwise; log resolved strategy at INFO [REQ: auto-strategy-decision-rule]
- [x] 0.4 Lift the existing flat-decompose code (`planner.py:2674-2693`) into a first-class function `_run_serial_decompose(input_mode, input_path, ...)` returning a complete plan [REQ: serial-path-is-the-primary-code-path]
- [x] 0.5 Remove `DOMAIN_PARALLEL_MIN_REQS = 30` and any `req_count`-based strategy selection from `run_planning_pipeline` [REQ: legacy-req-count-heuristic-removed]
- [x] 0.6 Update `enrich_plan_metadata` to record `plan_method` as `serial` or `parallel` (replacing today's `api`) [REQ: strategy-is-recorded-in-plan-metadata]
- [x] 0.7 Add `strategy` field to every decompose-purpose `LLM_CALL` event payload [REQ: cost-telemetry-per-strategy]
- [x] 0.8 Unit test: directive `serial` invokes serial path only [REQ: planner-strategy-directive]
- [x] 0.9 Unit test: directive `parallel` invokes 3-phase path [REQ: planner-strategy-directive]
- [x] 0.10 Unit test: `auto` resolves to `serial` for a 45k-token estimate and `parallel` for a 145k estimate [REQ: auto-strategy-decision-rule]
- [x] 0.11 Unit test: estimator handles missing digest files without raising [REQ: token-estimator-does-not-invoke-claude]
- [x] 0.12 Integration: serial path produces a plan that passes `validate_plan` with the same constraints as the parallel path [REQ: serial-path-is-the-primary-code-path]

## 0b. Tier A — Replan domain-plan reuse

- [x] 0b.1 Define `_compute_domain_input_hash(domain_summary, requirements_json, brief_json, conventions)` returning sha256 hex [REQ: domain-input-hashing]
- [x] 0b.2 Update `_save_domain_plans` to persist `domain_input_hashes` keyed by domain name [REQ: domain-input-hashes-persisted-alongside-plans]
- [x] 0b.3 Implement `load_saved_domain_plans(lineage_paths)` that returns `(brief, domain_plans, hashes)` or `None` on missing/malformed [REQ: replan-looks-up-saved-domain-plans]
- [x] 0b.4 In `_auto_replan_cycle` parallel path, call the loader before Phase 2; for each domain compute current hash and compare; reuse if matching [REQ: per-domain-reuse-decision]
- [ ] 0b.5 Update `_phase2_parallel_decompose` to accept a `reuse_map: dict[str, dict]` of pre-resolved domain plans and skip those domains in the executor [REQ: per-domain-reuse-decision]
- [x] 0b.6 Emit `REPLAN_REUSE` event with `{reused, redecomposed, total}` after the reuse decision [REQ: reuse-telemetry-in-llm-call-events]
- [ ] 0b.7 In the serial path, add whole-plan reuse check: if digest hash matches prior plan AND `replan_ctx.completed` is empty, skip Claude call [REQ: reuse-applies-to-serial-path-via-whole-plan-check]
- [x] 0b.8 Unit test: matching hashes → reuse for that domain; non-matching → re-decompose [REQ: per-domain-reuse-decision]
- [x] 0b.9 Unit test: brief change invalidates all domain hashes [REQ: per-domain-reuse-decision]
- [ ] 0b.10 Unit test: serial-path replan with unchanged digest and empty completed list skips the LLM call [REQ: reuse-applies-to-serial-path-via-whole-plan-check]
- [ ] 0b.11 Integration: replicate the multi-cycle retry pattern; assert second cycle re-decomposes only the affected domain [REQ: replan-looks-up-saved-domain-plans]

## 1. Tier A — Prompt-block refactor & cache breakpoints

- [ ] 1.1 Add a `ContentBlock` type alias in `lib/set_orch/templates.py` and document the canonical block order (tools → system+rules → digest → volatile) in a module docstring [REQ: cascade-invalidation-order-is-stable]
- [ ] 1.2 Refactor `render_planning_prompt` to return `list[ContentBlock]` with the four canonical blocks [REQ: planner-prompts-return-content-blocks]
- [ ] 1.3 Refactor `render_brief_prompt` (Phase 1) to return `list[ContentBlock]` with the canonical block order [REQ: planner-prompts-return-content-blocks]
- [ ] 1.4 Refactor `render_domain_decompose_prompt` (Phase 2) so tools and system+rules blocks are byte-identical across all parallel domain calls [REQ: phase-2-fan-out-shares-cache]
- [ ] 1.5 Refactor `render_merge_prompt` (Phase 3) to return `list[ContentBlock]` with the canonical block order [REQ: planner-prompts-return-content-blocks]
- [ ] 1.6 Refactor `_DIGEST_PROMPT_TEMPLATE` and the per-section variant in `lib/set_orch/digest.py` to return `list[ContentBlock]` [REQ: planner-prompts-return-content-blocks]
- [ ] 1.7 Set `cache_control={"type": "ephemeral", "ttl": "1h"}` on the tools/output-skeleton block of every planner-side prompt [REQ: cache-breakpoints-on-stable-layers]
- [ ] 1.8 Set `cache_control={"type": "ephemeral", "ttl": "1h"}` on the system+rules block of every planner-side prompt [REQ: cache-breakpoints-on-stable-layers]
- [ ] 1.9 Set `cache_control={"type": "ephemeral", "ttl": "5m"}` on the digest-stable block of every prompt that includes the digest [REQ: cache-breakpoint-on-digest-layer]
- [ ] 1.10 Ensure no `cache_control` is emitted on the volatile/replan-delta block [REQ: spec-tail-and-replan-delta-uncached]
- [ ] 1.11 Update `subprocess_utils.run_claude` to accept `list[ContentBlock]` and pass through to the Anthropic SDK without flattening to a string [REQ: planner-prompts-return-content-blocks]
- [ ] 1.12 Update every call site of `run_claude` in `planner.py`, `digest.py`, dispatcher, verifier to pass blocks [REQ: planner-prompts-return-content-blocks]
- [ ] 1.13 Record `cache_read_tokens` and `cache_create_tokens` in every planner-side `LLM_CALL` event payload, sourced from the SDK response [REQ: cache-observability-in-llm-call-events]
- [ ] 1.14 Add a unit test asserting block order is canonical for every render function [REQ: cascade-invalidation-order-is-stable]
- [ ] 1.15 Add a unit test asserting Phase 2 fan-out builds byte-identical first two blocks across N domain prompts [REQ: phase-2-fan-out-shares-cache]
- [ ] 1.16 Add an E2E scaffold test that runs a small spec twice and asserts ≥5× input-token reduction on the second run via cache_read_tokens [REQ: cache-observability-in-llm-call-events]

## 2. Tier A — Path memoization, log demote, lineage index

- [ ] 2.1 Wrap `LineagePaths.plan_path` and `LineagePaths.digest_dir` in `functools.lru_cache(maxsize=64)` keyed on `(state_file, lineage_id, request_kind)` [REQ: cascade-invalidation-order-is-stable]
- [ ] 2.2 Demote the `LineagePaths fallback` log line in `paths.py:451` and `paths.py:562` to TRACE-equivalent unless `SET_ORCH_VERBOSE=1` [REQ: cache-observability-in-llm-call-events]
- [ ] 2.3 Add `set/orchestration/lineage-index.json` produced incrementally on archive append; `compute_phase_offset` reads the index instead of scanning the JSONL [REQ: python-planning-orchestration]
- [ ] 2.4 Move memory hygiene off the per-poll path; rebuild a sorted-by-id duplicate-detection index incrementally on `remember`/`forget` MCP calls [REQ: python-planning-orchestration]

## 3. Tier B — Phase 2 hardening (parallel path only)

- [ ] 3.1 Add directives `planner.parallel.max_workers` (default 4), `planner.parallel.max_retries` (default 2), `planner.parallel.per_worker_timeout` (default 300), `planner.parallel.rate_limit_backoff` (default 30), `planner.parallel.merge_timeout` (default 1500) in `config.py` [REQ: configurable-parallel-worker-count]
- [ ] 3.2 Wrap each `_decompose_single_domain` call in `_phase2_parallel_decompose` with try/retry/exponential-backoff up to `max_retries` [REQ: phase-2-per-worker-retry-budget]
- [ ] 3.3 Apply `per_worker_timeout` to each Phase 2 future via `concurrent.futures` timeout; cancelled calls count as failed attempts [REQ: per-worker-timeout]
- [ ] 3.4 On final per-worker failure, emit `domain_plans[<domain>] = {"decompose_failed": true, "error": str(exc), "fallback_changes": []}` instead of empty domain plan [REQ: phase-2-per-worker-retry-budget]
- [ ] 3.5 Update `render_merge_prompt` to include any `decompose_failed` domains as explicit instructions for placeholder-change emission [REQ: phase-3-sees-explicit-failure-markers]
- [ ] 3.6 Reduce `_phase2_parallel_decompose` default ThreadPoolExecutor `max_workers` to 4 [REQ: configurable-parallel-worker-count]
- [ ] 3.7 Track per-worker failure timestamps; when ≥3 fail within 5 s, pause new dispatches for `rate_limit_backoff` seconds [REQ: phase-2-burst-failure-backoff]
- [ ] 3.8 Apply `merge_timeout` to the Phase 3 Claude call; log WARNING when call exceeds 600 s with elapsed-time + token snapshot [REQ: configurable-phase-3-timeout]
- [ ] 3.9 Unit test: injecting a Claude-call exception in one Phase 2 worker; assert other domains still complete, failed domain has `decompose_failed: true`, merge prompt receives the failure marker [REQ: phase-2-per-worker-retry-budget]
- [ ] 3.10 Unit test: 3 simultaneous worker errors trigger backoff, recovery succeeds [REQ: phase-2-burst-failure-backoff]

## 4. Tier B — Scoped replan patches

- [ ] 4.1 Add directive `replan_strategy: full | scoped_patch` (default `full`) in `config.py` [REQ: replan-strategy-directive]
- [ ] 4.2 Define patch JSON schema (`{patch_version, base_plan_version, operations: [{op, change?, name?, fields?}], reasoning}`) and a Python dataclass [REQ: scoped-replan-emits-plan-patches]
- [ ] 4.3 Add `render_scoped_patch_prompt` returning `list[ContentBlock]` with the canonical block order; the volatile block carries `(remaining_changes_dag, last_completed_summary, e2e_failures)` [REQ: scoped-replan-emits-plan-patches]
- [ ] 4.4 Add `_replan_scoped_patch_cycle` in `engine.py` alongside `_auto_replan_cycle`; routed by `replan_strategy` [REQ: replan-strategy-directive]
- [ ] 4.5 Implement patch validator that rejects: removal/modify of merged or running changes, duplicate adds, unknown names, stale `base_plan_version` [REQ: patch-validation-rejects-invalid-operations]
- [ ] 4.6 Implement atomic patch application under the state lock with single `plan_version` increment and rollback on mid-apply error [REQ: patch-application-is-atomic-under-state-lock]
- [ ] 4.7 On patch validation rejection, emit `PATCH_REJECTED` event and fall back to `_auto_replan_cycle()` with the same trigger context [REQ: fallback-to-full-replan-on-patch-failure]
- [ ] 4.8 Emit `PLAN_PATCHED` event with the operation count after successful apply [REQ: patch-application-is-atomic-under-state-lock]
- [ ] 4.9 Update `python-planning-orchestration` entry to accept `mode: "scoped_patch"` and route accordingly [REQ: python-planning-orchestration]
- [ ] 4.10 Unit test: validator rejects each invalid case and produces correct `PATCH_REJECTED` reasons [REQ: patch-validation-rejects-invalid-operations]
- [ ] 4.11 Unit test: atomic apply with mid-operation exception leaves state and `plan_version` unchanged [REQ: patch-application-is-atomic-under-state-lock]
- [ ] 4.12 Unit test: rejection path falls through to full-replan and emits both events [REQ: fallback-to-full-replan-on-patch-failure]

## 5. Tier B — Stall counter

- [ ] 5.1 Add `replan_stall_count: int` field to orchestration state with default 0 [REQ: stall-counter-bounds-unproductive-replans]
- [ ] 5.2 Add directive `max_consecutive_replans_without_progress` (default 0 = off) in `config.py` [REQ: stall-halts-replan-at-threshold]
- [ ] 5.3 After each replan apply, reset `replan_stall_count` to 0 if patch contains an `add` AND `len(operations) > 1`; otherwise increment [REQ: stall-counter-bounds-unproductive-replans]
- [ ] 5.4 Reset `replan_stall_count` to 0 on every `CHANGE_MERGED` event under the same state-lock window as the merge [REQ: stall-counter-bounds-unproductive-replans]
- [ ] 5.5 When `replan_stall_count >= max_consecutive_replans_without_progress > 0`, set status to `replan_stalled`, halt further replans, emit `REPLAN_STALL` sentinel finding [REQ: stall-halts-replan-at-threshold]
- [ ] 5.6 Add API endpoint `POST /api/<project>/orchestration/ack-stall` that transitions `replan_stalled` → `running` and resets the counter to 0 [REQ: stall-halts-replan-at-threshold]
- [ ] 5.7 Update `python-replan-respects-cycle-limits` enforcement to honor stall before retry/cycle limits [REQ: python-replan-respects-cycle-limits]
- [ ] 5.8 Unit test: productive vs unproductive patch increments the counter correctly [REQ: stall-counter-bounds-unproductive-replans]
- [ ] 5.9 Unit test: at threshold the orchestrator halts and the ack endpoint resumes [REQ: stall-halts-replan-at-threshold]

## 6. Tier B — JIT ambiguity resolution

- [ ] 6.1 Add directive `amb_resolution: inline | jit` (default `inline`) in `config.py` [REQ: ambiguities-attach-to-changes-in-jit-mode]
- [ ] 6.2 Add directive `models.amb_clarify` (default `sonnet`) in `model_config.py` [REQ: jit-model-is-configurable-and-cheaper-than-planner]
- [ ] 6.3 Update `_build_digest_content` so when `amb_resolution: jit`, deferred AMBs are NOT injected into the planner prompt [REQ: ambs-do-not-trigger-replan-in-jit-mode]
- [ ] 6.4 Update planner so changes in JIT mode carry `unresolved_ambiguities: [<id>, ...]` derived from `affects_requirements` mapping [REQ: ambiguities-attach-to-changes-in-jit-mode]
- [ ] 6.5 Update replan-trigger detection (`_detect_replan_trigger`) to ignore AMB-only conditions when `amb_resolution: jit` [REQ: ambs-do-not-trigger-replan-in-jit-mode]
- [ ] 6.6 Add `render_amb_clarify_prompt` returning a small `list[ContentBlock]` (≤2k tokens) listing each ambiguity by id, description, source [REQ: jit-clarification-call-when-agent-starts-work]
- [ ] 6.7 In dispatcher, before agent main-loop start, invoke clarification Claude call when change has non-empty `unresolved_ambiguities` and `amb_resolution: jit` [REQ: jit-clarification-call-when-agent-starts-work]
- [ ] 6.8 Parse clarification response; for each `resolution: "resolved"` entry, append `resolution_note` under a "Resolved Ambiguities" footer in the change scope [REQ: jit-clarification-call-when-agent-starts-work]
- [ ] 6.9 Journal each clarification result in the change's events stream [REQ: jit-clarification-call-when-agent-starts-work]
- [ ] 6.10 For any `resolution: "human"` entry, pause the change with status `awaiting_clarification` and emit a sentinel finding [REQ: jit-clarification-call-when-agent-starts-work]
- [ ] 6.11 Add a digest regression test asserting `triage.md` and `coverage.json` are byte-equivalent across `amb_resolution: jit` and `amb_resolution: inline` on the same fixed spec [REQ: triage-md-is-unchanged-across-modes]

## 7. Tier B — Phase 3 map-reduce

- [ ] 7.1 Add directive `merge_strategy: single | map_reduce` (default `single`) in `config.py` [REQ: phase-3-map-reduce-for-large-merges]
- [ ] 7.2 Implement pair-wise reduce stage: deterministic ordering by domain name, in-flight cap of 2, model `decompose_merge_reduce` (default Sonnet) [REQ: phase-3-map-reduce-for-large-merges]
- [ ] 7.3 Each reduce step output schema includes `gaps[]` and `conflicts[]` channels (Structured Information Protocol) [REQ: phase-3-map-reduce-for-large-merges]
- [ ] 7.4 Implement final synthesizer (Opus) call that merges reduced halves and addresses every gap with a placeholder change [REQ: phase-3-map-reduce-for-large-merges]
- [ ] 7.5 Threshold logic: when `merge_strategy: map_reduce` AND (`domain_count > 8` OR sum-of-domain-plan-JSON-chars > 80000), use map-reduce; otherwise single [REQ: phase-3-map-reduce-for-large-merges]
- [ ] 7.6 Unit test on a synthetic 12-domain plan asserting deterministic pair ordering and gap propagation [REQ: phase-3-map-reduce-for-large-merges]

## 8. Tier B — Event-driven post-merge replan

- [ ] 8.1 Identify pending downstream changes (those with merged change in `depends_on`) inside the merge handler [REQ: event-driven-post-merge-scoped-replan-trigger]
- [ ] 8.2 When `replan_strategy: scoped_patch` AND any downstream changes are pending, invoke a scoped-patch call with `target_changes: <downstream>` synchronously inside the merge handler [REQ: event-driven-post-merge-scoped-replan-trigger]
- [ ] 8.3 Ensure the scoped call runs on the main monitor loop, not in a thread [REQ: event-driven-post-merge-scoped-replan-trigger]
- [ ] 8.4 Unit test: merge with downstream pending → scoped call invoked; merge without downstream → no replan invoked [REQ: event-driven-post-merge-scoped-replan-trigger]

## 9. Tier C — Diff-update digest

- [ ] 9.1 Add directive `digest_strategy: full | diff_update` (default `full`) in `config.py` [REQ: digest-delegates-to-per-section-pipeline-when-enabled]
- [ ] 9.2 Implement section identifier resolution: prefer set-spec-capture metadata, fallback to markdown headings, fallback to single-section [REQ: section-identification]
- [ ] 9.3 Implement section content normalization (strip trailing whitespace, normalize newlines to `\n`) and `sha256` hashing [REQ: section-content-hashing]
- [ ] 9.4 Implement per-section storage at `set/orchestration/digest/sections/<section-id>.json` with schema `{section_id, content_hash, requirements, ambiguities, coverage_hints, gaps}` [REQ: section-storage-co-located-with-digest-cache]
- [ ] 9.5 Implement per-section Claude call (`render_section_digest_prompt`, default model Sonnet) for changed sections only [REQ: spec-edit-triggers-selective-re-digest]
- [ ] 9.6 On hash match, reuse existing section file and log INFO `digest section <id> reused (hash match)` [REQ: section-content-hashing]
- [ ] 9.7 Implement deterministic Python reducer that merges per-section outputs into `requirements.json`, `coverage.json`, `triage.md` with stable ordering [REQ: deterministic-python-reducer]
- [ ] 9.8 Reducer dedupes gap entries by `(requirement_id, reason)` pair and emits all of them [REQ: deterministic-python-reducer]
- [ ] 9.9 Reducer fails with descriptive error on schema-violating section file; SHALL NOT produce partial outputs [REQ: deterministic-python-reducer]
- [ ] 9.10 Wire `digest_strategy: diff_update` to invoke per-section pipeline; ensure existing output paths under `set/orchestration/digest/` remain unchanged [REQ: backward-compatible-output-paths]
- [ ] 9.11 Update `python-digest-api-invocation` requirement: digest prompts pass `list[ContentBlock]` with cache_control [REQ: python-digest-api-invocation]
- [ ] 9.12 Determinism test: invoke reducer twice on the same section files; assert byte-identical `requirements.json`, `coverage.json`, `triage.md` outputs [REQ: deterministic-python-reducer]
- [ ] 9.13 Selective re-digest test: edit one section, re-run; assert only that section's Claude call fires; assert other sections are reused [REQ: spec-edit-triggers-selective-re-digest]
- [ ] 9.14 Cross-project isolation test: two projects with identical spec content have separate `digest/sections/` dirs [REQ: section-storage-co-located-with-digest-cache]

## 10. Tier C — Hierarchical retrieval & cost-optimized model preset

- [ ] 10.1 Tag each requirement with `domain` and `also_affects_domains` in `requirements.json` (already present per spec but enforce) [REQ: hierarchical-retrieval-into-phase-2-prompts]
- [ ] 10.2 In Phase 2 prompt builder, retrieve domain-tagged + cross-cutting requirements; replace other-domain requirements with one-line `REQ-<id>: <title>` summaries [REQ: hierarchical-retrieval-into-phase-2-prompts]
- [ ] 10.3 Extend `cost-optimized` model preset in `model_config.py` to use Haiku for `decompose_brief` and `decompose_domain` when `requirement_count < 20` [REQ: jit-model-is-configurable-and-cheaper-than-planner]
- [ ] 10.4 Unit test: cross-cutting requirement is present in every affected domain's Phase 2 prompt; non-affecting requirement appears as one-line summary only [REQ: hierarchical-retrieval-into-phase-2-prompts]

## 11. Validation gates

- [ ] 11.1 Tier A strategy: planner-pipeline scaffold; assert `auto` resolves to `serial` for a ≤80-req digest and `parallel` for a >180-req digest; explicit overrides work both ways [REQ: auto-strategy-decision-rule]
- [ ] 11.2 Tier A reuse: replicate the multi-cycle retry pattern; inject a single-domain change between cycles; assert only the affected domain re-runs Phase 2 on the second cycle [REQ: per-domain-reuse-decision]
- [ ] 11.3 Tier A caching: run a small spec twice; assert ≥5× input-token reduction on the second run via cache_read_tokens (measured from `LLM_CALL` events) [REQ: cache-observability-in-llm-call-events]
- [ ] 11.4 Tier B Phase 2 hardening: force `planner.strategy: parallel`, inject worker fault, assert no silent empty domain and `decompose_failed` marker present [REQ: phase-2-per-worker-retry-budget]
- [ ] 11.5 Tier B burst-failure: inject 3 simultaneous worker errors, assert backoff fires and recovery succeeds [REQ: phase-2-burst-failure-backoff]
- [ ] 11.6 Tier C acceptance: large-spec scaffold (≥20 domains, ≥150 reqs), assert time-to-first-merge ≥30 % improvement and planner-side tokens ≥50 % reduction [REQ: deterministic-python-reducer]
- [ ] 11.7 Gap-analysis regression test: deterministic byte-comparison of `coverage.json` + `triage.md` before/after each tier on a fixed spec [REQ: triage-md-is-unchanged-across-modes]
- [ ] 11.8 Cost regression: 13-domain digest re-decomposed 3 times costs ≤$5 total planner-side (sum `LLM_CALL.cost_usd` for decompose-purpose events) [REQ: cache-observability-in-llm-call-events]

## Acceptance Criteria (from spec scenarios)

### planner-prompt-caching

- [ ] AC-1: WHEN `render_planning_prompt(...)` is called THEN it returns a list with at least four blocks ordered: tools/output-skeleton, system+rules, digest-stable, spec-tail [REQ: planner-prompts-return-content-blocks, scenario: planning-prompt-builder-returns-blocks]
- [ ] AC-2: WHEN `planner.run_planning_pipeline()` invokes Claude with the rendered blocks THEN `subprocess_utils.run_claude()` passes the blocks through to the Anthropic SDK without flattening to a string [REQ: planner-prompts-return-content-blocks, scenario: caller-passes-blocks-to-claude]
- [ ] AC-3: WHEN any planner-side prompt is built THEN the first content block (tools schema + JSON output skeleton) carries `cache_control={"type": "ephemeral", "ttl": "1h"}` [REQ: cache-breakpoints-on-stable-layers, scenario: tools-layer-cached-with-1h-ttl]
- [ ] AC-4: WHEN any planner-side prompt is built THEN the system+rules block carries `cache_control={"type": "ephemeral", "ttl": "1h"}` [REQ: cache-breakpoints-on-stable-layers, scenario: system-rules-layer-cached-with-1h-ttl]
- [ ] AC-5: WHEN a prompt includes the digest content THEN the digest-stable block carries `cache_control={"type": "ephemeral", "ttl": "5m"}` [REQ: cache-breakpoint-on-digest-layer, scenario: digest-layer-cached-with-5m-ttl]
- [ ] AC-6: WHEN a prompt is built with replan context or per-cycle spec tail THEN that block is emitted without a `cache_control` field [REQ: spec-tail-and-replan-delta-uncached, scenario: volatile-block-has-no-cache-control]
- [ ] AC-7: WHEN the test suite runs the block-order test THEN every render function output matches the canonical order [REQ: cascade-invalidation-order-is-stable, scenario: block-order-assertion-in-ci]
- [ ] AC-8: WHEN `_phase2_parallel_decompose` builds prompts for N domains THEN the first two blocks are identical across all N prompts [REQ: phase-2-fan-out-shares-cache, scenario: per-domain-prompts-differ-only-in-volatile-section]
- [ ] AC-9: WHEN the planner emits an `LLM_CALL` event THEN payload includes `cache_read_tokens` and `cache_create_tokens` integer fields (zero when absent) [REQ: cache-observability-in-llm-call-events, scenario: llm-call-event-includes-cache-token-fields]

### replan-scoped-patch

- [ ] AC-10: WHEN `_handle_auto_replan` runs with `replan_strategy=scoped_patch` THEN the planner returns `{patch_version, base_plan_version, operations, reasoning}` with named ops [REQ: scoped-replan-emits-plan-patches, scenario: patch-shape-on-scoped-replan]
- [ ] AC-11: WHEN the planner runs the initial decompose (no prior plan) THEN it produces a full plan regardless of `replan_strategy` [REQ: scoped-replan-emits-plan-patches, scenario: initial-plan-unaffected]
- [ ] AC-12: WHEN a patch contains `remove` of a merged change THEN it is rejected and orchestrator falls back to full replan with `PATCH_REJECTED` event reason `"remove of merged change"` [REQ: patch-validation-rejects-invalid-operations, scenario: reject-removal-of-merged-change]
- [ ] AC-13: WHEN a patch contains `add` with an existing name THEN it is rejected with reason `"duplicate add"` [REQ: patch-validation-rejects-invalid-operations, scenario: reject-duplicate-add]
- [ ] AC-14: WHEN a patch declares a stale `base_plan_version` THEN it is rejected with reason `"stale base_plan_version"` [REQ: patch-validation-rejects-invalid-operations, scenario: reject-stale-base-version]
- [ ] AC-15: WHEN a validated patch with N operations is applied THEN the orchestrator holds the state lock for the entire sequence, increments `plan_version` exactly once, and emits a single `PLAN_PATCHED` event [REQ: patch-application-is-atomic-under-state-lock, scenario: atomic-patch-application]
- [ ] AC-16: WHEN an operation in the patch raises during apply THEN the orchestrator rolls back prior operations, leaves the state file unchanged, and emits `PATCH_FAILED` with the failing index [REQ: patch-application-is-atomic-under-state-lock, scenario: mid-apply-error-rolls-back]
- [ ] AC-17: WHEN a patch is rejected by the validator THEN the orchestrator invokes `_auto_replan_cycle()` with the same trigger context and both LLM costs are observable [REQ: fallback-to-full-replan-on-patch-failure, scenario: validation-rejection-triggers-full-replan]
- [ ] AC-18: WHEN a replan applies a patch with `add` plus other ops THEN `replan_stall_count` is set to 0 [REQ: stall-counter-bounds-unproductive-replans, scenario: productive-replan-resets-counter]
- [ ] AC-19: WHEN a replan applies a patch with only `modify` ops THEN `replan_stall_count` increments by 1 [REQ: stall-counter-bounds-unproductive-replans, scenario: unproductive-replan-increments-counter]
- [ ] AC-20: WHEN a `CHANGE_MERGED` event fires THEN `replan_stall_count` resets to 0 in the same state-lock window as the merge [REQ: stall-counter-bounds-unproductive-replans, scenario: merge-resets-counter]
- [ ] AC-21: WHEN `max_consecutive_replans_without_progress = 2` AND `replan_stall_count = 2` THEN status becomes `replan_stalled`, a `REPLAN_STALL` sentinel finding fires, and no further replan attempts are made [REQ: stall-halts-replan-at-threshold, scenario: stall-threshold-reached]
- [ ] AC-22: WHEN `max_consecutive_replans_without_progress = 0` THEN the stall halt never fires regardless of counter value [REQ: stall-halts-replan-at-threshold, scenario: stall-counter-disabled-by-default]
- [ ] AC-23: WHEN an operator POSTs the stall-acknowledgment endpoint while status is `replan_stalled` THEN status transitions to `running` and the counter resets to 0 [REQ: stall-halts-replan-at-threshold, scenario: operator-acknowledgment-resumes-replan]

### amb-jit-resolution

- [ ] AC-24: WHEN digest produces ambiguities with `affects_requirements: ["REQ-AUTH-001"]` AND `amb_resolution: jit` AND change `auth-foundation` includes `REQ-AUTH-001` THEN `auth-foundation.unresolved_ambiguities` contains the ambiguity id [REQ: ambiguities-attach-to-changes-in-jit-mode, scenario: jit-mode-populates-per-change-list]
- [ ] AC-25: WHEN `amb_resolution: inline` THEN the planner prompt contains the existing "Deferred Ambiguities" section and changes do NOT carry `unresolved_ambiguities` [REQ: ambiguities-attach-to-changes-in-jit-mode, scenario: inline-mode-unchanged-default]
- [ ] AC-26: WHEN the same spec is digested with `amb_resolution: jit` then with `amb_resolution: inline` THEN `triage.md` and `coverage.json` are byte-identical [REQ: triage-md-is-unchanged-across-modes, scenario: gap-analysis-byte-equivalence]
- [ ] AC-27: WHEN `dispatcher.dispatch_change()` runs for a change with non-empty `unresolved_ambiguities` AND `amb_resolution: jit` THEN the dispatcher invokes the clarification Claude call before the agent's main loop with parsed response shape [REQ: jit-clarification-call-when-agent-starts-work, scenario: clarification-call-invoked-on-dispatch]
- [ ] AC-28: WHEN clarification returns `resolution: "resolved"` THEN the `resolution_note` is appended under a "Resolved Ambiguities" footer in the change scope and journalled [REQ: jit-clarification-call-when-agent-starts-work, scenario: resolution-patched-into-change-scope]
- [ ] AC-29: WHEN clarification returns `resolution: "human"` for any ambiguity THEN the change is paused with status `awaiting_clarification` and a sentinel finding is emitted [REQ: jit-clarification-call-when-agent-starts-work, scenario: human-escalation-pauses-dispatch]
- [ ] AC-30: WHEN `amb_resolution: jit` AND digest contains 5 unresolved ambiguities AND no other replan trigger condition is met THEN the auto-replan loop does not fire [REQ: ambs-do-not-trigger-replan-in-jit-mode, scenario: ambiguity-does-not-trigger-replan]
- [ ] AC-31: WHEN `amb_resolution: inline` AND digest contains unresolved ambiguities THEN replan trigger detection behaves as today [REQ: ambs-do-not-trigger-replan-in-jit-mode, scenario: ambiguity-triggers-replan-in-inline-mode]
- [ ] AC-32: WHEN no `models.amb_clarify` is configured THEN the JIT call uses Sonnet [REQ: jit-model-is-configurable-and-cheaper-than-planner, scenario: default-model-is-sonnet]
- [ ] AC-33: WHEN `models.amb_clarify: haiku` is configured THEN the JIT call uses Haiku [REQ: jit-model-is-configurable-and-cheaper-than-planner, scenario: override-via-directive]

### digest-diff-update

- [ ] AC-34: WHEN the spec was produced by set-spec-capture AND section ids are present THEN the digest uses those ids [REQ: section-identification, scenario: set-spec-capture-segmentation-used]
- [ ] AC-35: WHEN no set-spec-capture metadata AND the spec contains `##` headings THEN each `##` heading defines a section with kebab-case id deduplicated by suffix [REQ: section-identification, scenario: markdown-heading-fallback]
- [ ] AC-36: WHEN the spec has no metadata and no headings THEN the entire file is one section with id `<filename-stem>` [REQ: section-identification, scenario: single-section-fallback]
- [ ] AC-37: WHEN a section is digested for the first time THEN `digest/sections/<section-id>.json` contains the schema fields including `content_hash` [REQ: section-content-hashing, scenario: hash-stored-with-section-output]
- [ ] AC-38: WHEN an existing section file's `content_hash` matches the recomputed hash THEN the system reuses it without invoking Claude and logs INFO reuse line [REQ: section-content-hashing, scenario: hash-matches-reuse]
- [ ] AC-39: WHEN an existing section file's hash does not match THEN the system invokes per-section Claude (default Sonnet) and overwrites the file [REQ: section-content-hashing, scenario: hash-differs-recompute]
- [ ] AC-40: WHEN the reducer is invoked twice on the same section files THEN output bytes of `requirements.json`, `coverage.json`, `triage.md` are identical between runs [REQ: deterministic-python-reducer, scenario: reducer-is-deterministic]
- [ ] AC-41: WHEN two sections each report a gap for the same requirement id with different reasons THEN both are emitted, deduplicated by `(requirement_id, reason)` pair [REQ: deterministic-python-reducer, scenario: gaps-are-unioned-not-overwritten]
- [ ] AC-42: WHEN a section file is missing a required field THEN the reducer fails with a descriptive error and produces no partial output [REQ: deterministic-python-reducer, scenario: reducer-fails-on-schema-violation]
- [ ] AC-43: WHEN the planner reads `set/orchestration/digest/requirements.json` THEN it finds the file at the same path with the same JSON shape as before [REQ: backward-compatible-output-paths, scenario: existing-consumers-unaffected]
- [ ] AC-44: WHEN the spec is edited in section `auth` only AND re-digest is invoked THEN only `auth` triggers a per-section Claude call AND others are reused AND the reducer re-merges [REQ: spec-edit-triggers-selective-re-digest, scenario: single-section-edit]
- [ ] AC-45: WHEN two projects digest specs with identical content THEN each has its own `digest/sections/` directory and they are not shared via the global cache [REQ: section-storage-co-located-with-digest-cache, scenario: sections-stored-per-project]

### orch-plan-python (modified + added)

- [ ] AC-46: WHEN a domain decompose call raises a transient exception THEN the worker retries up to `max_retries` with exponential backoff (1s, 2s, 4s) [REQ: phase-2-per-worker-retry-budget, scenario: transient-worker-failure-recovers]
- [ ] AC-47: WHEN a domain decompose fails on every attempt THEN `domain_plans[<domain>] = {"decompose_failed": true, "error": ..., "fallback_changes": []}` and no exception escapes the executor [REQ: phase-2-per-worker-retry-budget, scenario: all-retries-exhausted]
- [ ] AC-48: WHEN a domain decompose call exceeds `per_worker_timeout` THEN it is cancelled, counted as a failed attempt, and retry logic applies [REQ: per-worker-timeout, scenario: worker-timeout-treated-as-failure]
- [ ] AC-49: WHEN Phase 2 reports `decompose_failed: true` for domain `auth` THEN the Phase 3 merge prompt contains a directive to include a placeholder change AND the resulting plan contains a change with scope starting `[REDECOMPOSE_NEEDED] auth` [REQ: phase-3-sees-explicit-failure-markers, scenario: failed-domain-produces-visible-placeholder]
- [ ] AC-50: WHEN no `planner.parallel.max_workers` is configured AND there are 13 domains THEN the executor uses 4 workers [REQ: configurable-parallel-worker-count, scenario: default-workers]
- [ ] AC-51: WHEN `planner.parallel.max_workers: 6` is configured AND there are 13 domains THEN the executor uses 6 workers [REQ: configurable-parallel-worker-count, scenario: override-workers]
- [ ] AC-52: WHEN `domain_count <= 8` AND total scope chars `<= 80000` THEN Phase 3 runs as a single Claude call [REQ: phase-3-map-reduce-for-large-merges, scenario: single-call-merge-below-threshold]
- [ ] AC-53: WHEN `merge_strategy: map_reduce` AND `domain_count > 8` THEN Phase 3 runs pair-wise merges deterministically ordered by domain name AND the synthesizer addresses every gap [REQ: phase-3-map-reduce-for-large-merges, scenario: map-reduce-above-threshold]
- [ ] AC-54: WHEN Phase 2 builds a prompt for domain `cart` THEN domain-tagged + cross-cutting requirements are full text AND other-domain requirements are one-line summaries only [REQ: hierarchical-retrieval-into-phase-2-prompts, scenario: domain-prompt-content]
- [ ] AC-55: WHEN `auto_replan_cycle()` runs with `replan_strategy: full` THEN it calls `planner.run_planning_pipeline(mode="full", ...)` [REQ: python-planning-orchestration, scenario: planning-from-python-replan-full]
- [ ] AC-56: WHEN `auto_replan_cycle()` runs with `replan_strategy: scoped_patch` THEN it calls `planner.run_planning_pipeline(mode="scoped_patch", ...)` and the pipeline invokes patch validation [REQ: python-planning-orchestration, scenario: planning-from-python-replan-scoped-patch]

### orch-replan-python (modified + added)

- [ ] AC-57: WHEN no `replan_strategy` is configured THEN `_handle_auto_replan()` calls `_auto_replan_cycle()` (full replan) [REQ: replan-strategy-directive, scenario: default-strategy-is-full]
- [ ] AC-58: WHEN `replan_strategy: scoped_patch` THEN `_handle_auto_replan()` invokes the scoped-patch path and falls back to full on validation failure [REQ: replan-strategy-directive, scenario: scoped-patch-strategy]
- [ ] AC-59: WHEN change `auth-foundation` merges AND `user-profile` has it in `depends_on` AND `replan_strategy: scoped_patch` THEN merge handler invokes scoped-patch with `target_changes: ["user-profile"]` synchronously on the main loop [REQ: event-driven-post-merge-scoped-replan-trigger, scenario: downstream-change-replanned-post-merge]
- [ ] AC-60: WHEN a change merges AND no pending change has it in `depends_on` THEN no post-merge scoped replan is invoked [REQ: event-driven-post-merge-scoped-replan-trigger, scenario: no-downstream-changes-no-replan]
- [ ] AC-61: WHEN replan cycle count reaches `max_replan_cycles` THEN status becomes `done` with `replan_limit_reached: true` and no further replanning [REQ: python-replan-respects-cycle-limits, scenario: cycle-limit-reached]
- [ ] AC-62: WHEN a replan attempt fails THEN `replan_attempt` increments, retry after 30 s delay, give up after `MAX_REPLAN_RETRIES` consecutive failures [REQ: python-replan-respects-cycle-limits, scenario: replan-failure-with-retry]
- [ ] AC-63: WHEN `replan_stall_count >= max_consecutive_replans_without_progress > 0` THEN status becomes `replan_stalled`, no further replans, `REPLAN_STALL` sentinel finding emitted [REQ: python-replan-respects-cycle-limits, scenario: stall-threshold-reached]

### orch-digest-python (modified + added)

- [ ] AC-64: WHEN `digest_strategy: diff_update` AND digest is invoked THEN the system executes the per-section pipeline (section identification, hashing, per-section calls for changed sections, deterministic reducer) [REQ: digest-delegates-to-per-section-pipeline-when-enabled, scenario: diff-update-strategy-invoked]
- [ ] AC-65: WHEN no `digest_strategy` is configured OR `digest_strategy: full` THEN the system runs the full-spec Claude digest as today [REQ: digest-delegates-to-per-section-pipeline-when-enabled, scenario: default-strategy-unchanged]
- [ ] AC-66: WHEN `amb_resolution: jit` AND digest produces unresolved ambiguities AND no other replan trigger met THEN the auto-replan loop does not fire [REQ: replan-trigger-detection-no-longer-fires-on-ambs-alone-in-jit-mode, scenario: ambs-no-longer-trigger-replan-in-jit-mode]
- [ ] AC-67: WHEN `amb_resolution: inline` THEN AMBs continue to flow into the planner prompt as today [REQ: replan-trigger-detection-no-longer-fires-on-ambs-alone-in-jit-mode, scenario: inline-mode-preserves-todays-behavior]
- [ ] AC-68: WHEN the digest prompt blocks are sent to Claude THEN the response is parsed as JSON containing requirements, ambiguities, and coverage data [REQ: python-digest-api-invocation, scenario: successful-api-call]
- [ ] AC-69: WHEN the Claude API call fails or returns non-JSON THEN the system logs the error and returns a failure status without crashing [REQ: python-digest-api-invocation, scenario: api-failure]
- [ ] AC-70: WHEN the digest API call returns THEN `cache_read_tokens` and `cache_create_tokens` are recorded in the `LLM_CALL` event [REQ: python-digest-api-invocation, scenario: cache-observability]

### planner-strategy-routing

- [ ] AC-71: WHEN no `planner.strategy` is configured anywhere THEN `run_planning_pipeline()` resolves the strategy via the `auto` decision rule [REQ: planner-strategy-directive, scenario: default-strategy-is-auto]
- [ ] AC-72: WHEN `planner.strategy: serial` is configured THEN the pipeline executes the single-call (flat) decompose path regardless of digest size and does not invoke any of the 3 phase functions [REQ: planner-strategy-directive, scenario: explicit-serial-forces-single-call]
- [ ] AC-73: WHEN `planner.strategy: parallel` is configured THEN the pipeline executes `_try_domain_parallel_decompose` regardless of digest size [REQ: planner-strategy-directive, scenario: explicit-parallel-forces-3-phase]
- [ ] AC-74: WHEN `planner.strategy: auto` AND `estimate_flat_prompt_tokens()` returns 45000 THEN the system routes to `serial` [REQ: auto-strategy-decision-rule, scenario: small-digest-routes-to-serial]
- [ ] AC-75: WHEN `planner.strategy: auto` AND `estimate_flat_prompt_tokens()` returns 145000 THEN the system routes to `parallel` [REQ: auto-strategy-decision-rule, scenario: large-digest-routes-to-parallel]
- [ ] AC-76: WHEN the auto strategy decision is made THEN the system logs at INFO `planner.strategy=auto resolved=<...> estimated_tokens=<N> threshold=<T>` [REQ: auto-strategy-decision-rule, scenario: decision-is-logged]
- [ ] AC-77: WHEN `planner.single_call_max_input_tokens: 80000` is configured THEN the auto rule uses 80000 as the threshold [REQ: auto-strategy-decision-rule, scenario: threshold-override-via-directive]
- [ ] AC-78: WHEN `estimate_flat_prompt_tokens(...)` is called THEN it sums digest file byte sizes plus fixed overhead, divides by 3.5, returns an integer, never invokes Claude [REQ: token-estimator-does-not-invoke-claude, scenario: estimator-reads-digest-files]
- [ ] AC-79: WHEN the digest directory is missing a standard file THEN the estimator treats its size as 0 and does not raise [REQ: token-estimator-does-not-invoke-claude, scenario: estimator-handles-missing-files-gracefully]
- [ ] AC-80: WHEN `replan_ctx` is non-empty THEN the estimate adds the byte size of the serialized replan_ctx [REQ: token-estimator-does-not-invoke-claude, scenario: estimator-includes-replan-context]
- [ ] AC-81: WHEN a digest has 50 reqs AND `auto` AND estimate ≤ threshold THEN system routes to serial regardless of req_count [REQ: legacy-req-count-heuristic-removed, scenario: req-count-alone-does-not-force-parallel]
- [ ] AC-82: WHEN `planner.strategy` resolves to `serial` THEN `run_planning_pipeline()` calls `_run_serial_decompose(...)` directly, not via except-fallback [REQ: serial-path-is-the-primary-code-path, scenario: serial-path-is-named-and-reachable]
- [ ] AC-83: WHEN the serial path completes THEN the returned plan dict has the same top-level keys (`changes`, `phase_detected`, `reasoning`) and passes `validate_plan()` [REQ: serial-path-is-the-primary-code-path, scenario: serial-path-produces-same-plan-shape-as-parallel]
- [ ] AC-84: WHEN the serial path completes THEN `orchestration-plan.json::plan_method` equals `serial` [REQ: strategy-is-recorded-in-plan-metadata, scenario: plan-records-serial-method]
- [ ] AC-85: WHEN the parallel path completes THEN `orchestration-plan.json::plan_method` equals `parallel` [REQ: strategy-is-recorded-in-plan-metadata, scenario: plan-records-parallel-method]
- [ ] AC-86: WHEN any decompose-purpose `LLM_CALL` event is emitted THEN the payload includes a `strategy` field with the resolved value [REQ: cost-telemetry-per-strategy, scenario: llm-call-events-include-strategy-tag]

### replan-domain-plan-reuse

- [ ] AC-87: WHEN a replan fires AND `domains-plans-<lineage>.json` exists with valid JSON THEN the system loads `brief` and `domain_plans` and logs `replan: loaded saved domain plans (<N> domains)` [REQ: replan-looks-up-saved-domain-plans, scenario: saved-file-present-and-valid]
- [ ] AC-88: WHEN the saved file is missing THEN the system proceeds with a full Phase 1 + Phase 2 run without raising [REQ: replan-looks-up-saved-domain-plans, scenario: saved-file-missing]
- [ ] AC-89: WHEN the saved file exists but is malformed JSON THEN the system logs WARNING and proceeds with a full run [REQ: replan-looks-up-saved-domain-plans, scenario: saved-file-unparseable]
- [ ] AC-90: WHEN the same hash inputs are hashed twice THEN the resulting sha256 hex digests are byte-identical [REQ: domain-input-hashing, scenario: hash-function-determinism]
- [ ] AC-91: WHEN the hash is computed for domain `auth` THEN the hashed bytes are `domain_summary || \n || requirements_json || \n || brief_json || \n || conventions` (UTF-8) in fixed order [REQ: domain-input-hashing, scenario: hash-inputs-are-ordered]
- [ ] AC-92: WHEN domain `cart` has saved hash matching current hash THEN the system reuses `saved_domain_plans["cart"]`, does not invoke `_decompose_single_domain`, logs `replan: domain cart reused (hash match)` [REQ: per-domain-reuse-decision, scenario: unchanged-domain-reused]
- [ ] AC-93: WHEN domain `auth` has saved hash differing from current hash THEN the system invokes `_decompose_single_domain` and includes it in the Phase 2 fan-out [REQ: per-domain-reuse-decision, scenario: changed-domain-re-decomposed]
- [ ] AC-94: WHEN the new planning brief differs from the saved brief THEN every domain hash recomputes to a different value and every domain is re-decomposed [REQ: per-domain-reuse-decision, scenario: brief-change-invalidates-all-domains]
- [ ] AC-95: WHEN `_save_domain_plans` runs after a successful Phase 2 THEN the resulting JSON has shape `{"brief": ..., "domain_plans": ..., "domain_input_hashes": {...}, "created_at": "..."}` [REQ: domain-input-hashes-persisted-alongside-plans, scenario: saved-file-shape-includes-hashes]
- [ ] AC-96: WHEN a replan reuses 11 of 13 domains THEN a `REPLAN_REUSE` event is emitted with payload `{"reused": 11, "redecomposed": 2, "total": 13}` [REQ: reuse-telemetry-in-llm-call-events, scenario: reuse-event-content]
- [ ] AC-97: WHEN serial path replan fires AND digest hash matches prior plan's hash AND `replan_ctx.completed` is empty THEN the path skips the Claude call, logs `replan: plan unchanged ...`, emits no decompose `LLM_CALL` [REQ: reuse-applies-to-serial-path-via-whole-plan-check, scenario: identical-replan-in-serial-mode]
- [ ] AC-98: WHEN digest content is unchanged BUT `replan_ctx.completed` is non-empty THEN the serial path invokes Claude [REQ: reuse-applies-to-serial-path-via-whole-plan-check, scenario: replan-context-forces-re-run-in-serial-mode]

### orch-plan-python (additional Tier A & burst-failure)

- [ ] AC-99: WHEN `run_planning_pipeline()` runs AND `planner.strategy` resolves to `serial` THEN it invokes `_run_serial_decompose(...)` directly and does not invoke any of the 3 phase functions [REQ: strategy-driven-dispatch, scenario: strategy-directive-routes-to-serial]
- [ ] AC-100: WHEN `planner.strategy` resolves to `parallel` THEN the pipeline invokes `_try_domain_parallel_decompose(...)` [REQ: strategy-driven-dispatch, scenario: strategy-directive-routes-to-parallel]
- [ ] AC-101: WHEN 3 worker failures occur within a 5 s window THEN the executor pauses new dispatches for `rate_limit_backoff` seconds and logs WARNING `Phase 2 burst-failure backoff active ...` [REQ: phase-2-burst-failure-backoff, scenario: burst-triggers-backoff]
- [ ] AC-102: WHEN the backoff period ends THEN retries resume with the existing per-worker exponential backoff schedule [REQ: phase-2-burst-failure-backoff, scenario: backoff-resumes-normally]
- [ ] AC-103: WHEN no `planner.parallel.merge_timeout` is configured THEN Phase 3 uses a 1500 s timeout [REQ: configurable-phase-3-timeout, scenario: default-timeout-is-1500-s]
- [ ] AC-104: WHEN Phase 3 has been running for more than 600 s THEN the system logs WARNING with elapsed-time and a token snapshot [REQ: configurable-phase-3-timeout, scenario: long-call-warning-fires]

### orch-replan-python (domain-plan reuse integration)

- [ ] AC-105: WHEN a replan fires after one change in `cart` merged AND `domains-plans-<lineage>.json` exists THEN only domains whose hash changed are re-decomposed AND `REPLAN_REUSE` event is emitted [REQ: replan-reuses-saved-domain-plans, scenario: single-domain-change-replans-only-that-domain]
- [ ] AC-106: WHEN serial mode AND digest input hash equals prior plan's hash AND `replan_ctx.completed` empty THEN system skips Claude, reuses prior plan, emits no decompose `LLM_CALL` [REQ: replan-reuses-saved-domain-plans, scenario: replan-in-serial-mode-reuses-prior-plan-when-stable]
