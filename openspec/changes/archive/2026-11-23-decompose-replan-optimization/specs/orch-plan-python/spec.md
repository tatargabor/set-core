## ADDED Requirements

### Requirement: Strategy-driven dispatch
`run_planning_pipeline()` SHALL select between serial and parallel decompose paths based on the resolved value of the `planner.strategy` directive (see capability `planner-strategy-routing`). The legacy `DOMAIN_PARALLEL_MIN_REQS = 30` heuristic SHALL be removed.

#### Scenario: Strategy directive routes to serial
- **WHEN** `run_planning_pipeline()` runs AND `planner.strategy` resolves to `serial`
- **THEN** the pipeline SHALL invoke `_run_serial_decompose(...)` directly
- **AND** SHALL NOT invoke `_phase1_planning_brief`, `_phase2_parallel_decompose`, or `_phase3_merge_plans`

#### Scenario: Strategy directive routes to parallel
- **WHEN** `run_planning_pipeline()` runs AND `planner.strategy` resolves to `parallel`
- **THEN** the pipeline SHALL invoke `_try_domain_parallel_decompose(...)`

### Requirement: Phase 2 burst-failure backoff
The `_phase2_parallel_decompose` executor SHALL track per-worker failure timestamps. When ≥3 workers fail within a 5-second window, new dispatches SHALL pause for `planner.parallel.rate_limit_backoff` seconds (default 30) before any retry.

#### Scenario: Burst triggers backoff
- **WHEN** 3 worker failures occur within a 5-second window
- **THEN** the executor SHALL pause new dispatches for `rate_limit_backoff` seconds
- **AND** SHALL log at WARNING level: `Phase 2 burst-failure backoff active (<N>s, after <K> failures in <T>s)`

#### Scenario: Backoff resumes normally
- **WHEN** the backoff period ends
- **THEN** retries SHALL resume with the existing per-worker exponential backoff schedule

### Requirement: Configurable Phase 3 timeout
The Phase 3 merge call SHALL use a configurable timeout `planner.parallel.merge_timeout` (default 1500 s, was hardcoded 1800 s). When the call exceeds 600 s, the system SHALL log a WARNING with the elapsed time and current token-budget snapshot.

#### Scenario: Default timeout is 1500 s
- **WHEN** no `planner.parallel.merge_timeout` is configured
- **THEN** Phase 3 SHALL use a 1500 s timeout

#### Scenario: Long-call warning fires
- **WHEN** Phase 3 has been running for more than 600 s
- **THEN** the system SHALL log a WARNING with elapsed-time and a token snapshot

### Requirement: Phase 2 per-worker retry budget
The Phase 2 parallel domain decompose (`_phase2_parallel_decompose` in `lib/set_orch/planner.py`) SHALL retry per-worker failures up to `planner.parallel.max_retries` times (default 2) with exponential backoff before marking the domain as failed.

#### Scenario: Transient worker failure recovers
- **WHEN** a domain decompose Claude call raises a transient exception (rate limit, network)
- **THEN** the worker SHALL retry up to `max_retries` times with exponential backoff (1 s, 2 s, 4 s)
- **AND** the final-attempt result SHALL be reported

#### Scenario: All retries exhausted
- **WHEN** a domain decompose fails on every attempt up to `max_retries`
- **THEN** the worker SHALL emit a `domain_plans[<domain>] = {"decompose_failed": true, "error": "<message>", "fallback_changes": []}` entry
- **AND** SHALL NOT raise out of the executor

### Requirement: Per-worker timeout
Each Phase 2 domain decompose call SHALL have a configurable timeout `planner.parallel.per_worker_timeout` (default 300 s). Timeouts count as a worker failure for retry purposes.

#### Scenario: Worker timeout treated as failure
- **WHEN** a domain decompose Claude call exceeds `per_worker_timeout`
- **THEN** the call SHALL be cancelled and counted as a failed attempt
- **AND** retry logic SHALL apply

### Requirement: Phase 3 sees explicit failure markers
The Phase 3 merge prompt (`render_merge_prompt`) SHALL include any `decompose_failed` domains as explicit instructions to emit a placeholder change with scope `[REDECOMPOSE_NEEDED] <domain>` so coverage gaps are visible.

#### Scenario: Failed domain produces visible placeholder
- **WHEN** Phase 2 reports `decompose_failed: true` for domain `auth`
- **THEN** the Phase 3 merge prompt SHALL contain a directive to include a placeholder change for the auth domain
- **AND** the resulting `orchestration-plan.json` SHALL contain a change with scope starting `[REDECOMPOSE_NEEDED] auth`

### Requirement: Configurable parallel worker count
The Phase 2 `ThreadPoolExecutor` SHALL use `min(domains, planner.parallel.max_workers)` workers, where `max_workers` defaults to 4.

#### Scenario: Default workers
- **WHEN** no `planner.parallel.max_workers` is configured AND there are 13 domains
- **THEN** the executor SHALL use 4 workers

#### Scenario: Override workers
- **WHEN** `planner.parallel.max_workers: 6` is configured AND there are 13 domains
- **THEN** the executor SHALL use 6 workers

### Requirement: Phase 3 map-reduce for large merges
When `merge_strategy: map_reduce` is configured AND `domain_count > 8` OR the total domain-plan JSON size exceeds 80,000 characters, Phase 3 SHALL execute as a two-stage pair-wise reduce: pair-wise merges (Sonnet, in-flight ≤ 2) followed by a final synthesizer call (Opus). Each reduce step's output SHALL include an explicit `gaps[]` channel.

#### Scenario: Single-call merge below threshold
- **WHEN** `domain_count <= 8` AND total scope chars `<= 80000`
- **THEN** Phase 3 SHALL run as today (single Claude call)

#### Scenario: Map-reduce above threshold
- **WHEN** `merge_strategy: map_reduce` AND `domain_count > 8`
- **THEN** Phase 3 SHALL run pair-wise merges deterministically ordered by domain name
- **AND** the final synthesizer SHALL receive each pair-wise output's `gaps[]` channel
- **AND** the synthesizer SHALL include a placeholder change for any unaddressed gap

### Requirement: Hierarchical retrieval into Phase 2 prompts
Phase 2 domain prompts SHALL receive only the domain-tagged requirements plus cross-cutting requirements (those with `also_affects_domains` including the domain). Other-domain requirements SHALL be present only as one-line summaries.

#### Scenario: Domain prompt content
- **WHEN** Phase 2 builds a prompt for domain `cart`
- **THEN** full requirement text for cart-domain requirements SHALL be present
- **AND** full requirement text for cross-cutting requirements that affect cart SHALL be present
- **AND** other-domain requirements SHALL appear only as `REQ-<id>: <one-line title>` lines

## MODIFIED Requirements

### Requirement: Python planning orchestration
The planning pipeline orchestration (input detection, freshness check, triage gate, Claude invocation, response parsing, plan enrichment) SHALL be available as a Python function callable from `auto_replan_cycle()` and from a `set-orch-core plan run` CLI command. The pipeline SHALL accept either a `mode: full` invocation (today's behavior, returns a complete plan) or a `mode: scoped_patch` invocation (returns a JSON patch against the current plan; see capability `replan-scoped-patch`).

#### Scenario: Planning from Python replan (full)
- **WHEN** `auto_replan_cycle()` runs with `replan_strategy: full`
- **THEN** it SHALL call `planner.run_planning_pipeline(mode="full", ...)` which orchestrates the full flow
- **AND** the pipeline SHALL use existing Python functions: `detect_test_infra()`, `build_decomposition_context()`, `validate_plan()`, `enrich_plan_metadata()`

#### Scenario: Planning from Python replan (scoped patch)
- **WHEN** `auto_replan_cycle()` runs with `replan_strategy: scoped_patch`
- **THEN** it SHALL call `planner.run_planning_pipeline(mode="scoped_patch", ...)` which produces a `{add, remove, modify}` patch
- **AND** the pipeline SHALL invoke patch validation before returning
