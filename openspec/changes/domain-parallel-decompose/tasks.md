# Tasks: domain-parallel-decompose

## 1. New prompt templates

- [x] 1.1 Add `render_brief_prompt()` to `templates.py` — takes domain summaries, dependencies, conventions, test infra, existing specs, active changes, memory context; outputs planning brief JSON schema [REQ: planning-brief-generation]
- [x] 1.2 Add `render_domain_decompose_prompt()` to `templates.py` — takes domain requirements, domain summary, planning brief, conventions, test infra, planning rules; outputs per-domain changes JSON schema with `external_dependencies` field [REQ: per-domain-parallel-decompose]
- [x] 1.3 Add `render_merge_prompt()` to `templates.py` — takes all domain plans, planning brief, dependencies.json, ambiguities context; outputs final orchestration-plan.json schema [REQ: merge-and-resolve-phase]

## 2. Phase 1 — Planning Brief

- [x] 2.1 Add `_phase1_planning_brief()` to `planner.py` — assembles brief context from digest data and calls Claude (opus) to produce the planning brief JSON [REQ: planning-brief-generation]
- [x] 2.2 Parse and validate the brief JSON output (domain_priorities, resource_ownership, cross_cutting_changes, phasing_strategy, domain_constraints) [REQ: planning-brief-generation]

## 3. Phase 2 — Domain Decompose (parallel)

- [x] 3.1 Add `_decompose_single_domain()` to `planner.py` — takes one domain's requirements + brief + conventions, calls Claude (opus), returns per-domain change list [REQ: per-domain-parallel-decompose]
- [x] 3.2 Add `_phase2_parallel_decompose()` — uses `ThreadPoolExecutor` to run `_decompose_single_domain()` for all domains in parallel (max 6 workers) [REQ: per-domain-parallel-decompose]
- [x] 3.3 Collect and validate per-domain results; fail entire Phase 2 if any domain call fails [REQ: per-domain-parallel-decompose]
- [x] 3.4 For non-digest mode (brief/spec input without domains), create a synthetic single domain containing all requirements and run through the same 3-phase flow [REQ: per-domain-parallel-decompose]

## 4. Phase 3 — Merge & Resolve

- [x] 4.1 Add `_phase3_merge_plans()` to `planner.py` — takes all domain plans + brief + dependencies, calls Claude (opus) to produce final unified plan [REQ: merge-and-resolve-phase]
- [x] 4.2 Resolve `external_dependencies` into `depends_on` edges — match each external dep to the change that owns that resource [REQ: merge-and-resolve-phase]
- [x] 4.3 Run existing `validate_plan()` on the merged output and `enrich_plan_metadata()` for hashes and cross-cutting ownership [REQ: merge-and-resolve-phase]

## 5. Pipeline integration

- [x] 5.1 Refactor `run_planning_pipeline()` to call Phase 1 → Phase 2 → Phase 3 in sequence, replacing the current single Claude call [REQ: planning-brief-generation]
- [x] 5.2 Write `orchestration-plan-domains.json` after Phase 2 — stores the brief and per-domain plans for selective replan [REQ: selective-replan]
- [x] 5.3 Preserve the return interface of `run_planning_pipeline()` — callers (engine.py) see no change [REQ: merge-and-resolve-phase]

## 6. Selective replan

- [x] 6.1 Update `_auto_replan_cycle()` in `engine.py` to detect replan trigger type (domain fail, E2E fail, spec change, coverage gap) [REQ: selective-replan]
- [x] 6.2 For domain-level failure: load `orchestration-plan-domains.json`, re-run Phase 2 for the failed domain only, then re-run Phase 3 [REQ: selective-replan]
- [x] 6.3 For E2E failure: re-run Phase 3 only with failure context added to the merge prompt [REQ: selective-replan]
- [x] 6.4 For spec change: re-run all 3 phases (full re-decompose) [REQ: selective-replan]
- [x] 6.5 For coverage gap: re-run Phase 2 for domains with uncovered reqs, then Phase 3 [REQ: selective-replan]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN run_planning_pipeline() is called in digest mode THEN Phase 1 produces a planning brief JSON with domain_priorities, resource_ownership, cross_cutting_changes, phasing_strategy [REQ: planning-brief-generation, scenario: brief-generation-from-digest]
- [x] AC-2: WHEN digest has one domain THEN brief still produced with empty cross_cutting_changes [REQ: planning-brief-generation, scenario: brief-generation-with-single-domain]
- [x] AC-3: WHEN Phase 2 executes THEN one opus call per domain runs in parallel via threading [REQ: per-domain-parallel-decompose, scenario: domain-decompose-execution]
- [x] AC-4: WHEN domain agent plans changes THEN it does not modify resources owned by other domains [REQ: per-domain-parallel-decompose, scenario: domain-agent-respects-resource-ownership]
- [x] AC-5: WHEN domain plans have external_dependencies THEN Phase 3 creates depends_on edges [REQ: merge-and-resolve-phase, scenario: cross-domain-dependency-resolution]
- [x] AC-6: WHEN two domains modify same resource THEN Phase 3 detects conflict and serializes [REQ: merge-and-resolve-phase, scenario: conflict-detection]
- [x] AC-7: WHEN merged plan complete THEN every requirement covered by at least one change [REQ: merge-and-resolve-phase, scenario: coverage-validation]
- [x] AC-8: WHEN Phase 3 outputs THEN format matches current orchestration-plan.json schema [REQ: merge-and-resolve-phase, scenario: output-format]
- [x] AC-9: WHEN change fails THEN only that domain re-runs Phase 2 + Phase 3 [REQ: selective-replan, scenario: domain-level-failure-triggers-domain-replan]
- [x] AC-10: WHEN E2E fails THEN only Phase 3 re-runs [REQ: selective-replan, scenario: e2e-failure-triggers-merge-only-replan]
