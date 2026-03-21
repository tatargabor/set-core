# Proposal: domain-parallel-decompose

## Why

The current decompose pipeline sends the entire spec (all domains, all requirements, all context) in a single Claude call. This works for small projects (~20 reqs) but degrades for larger ones — attention dilutes across 50K+ token inputs, cross-domain dependencies get missed, and requirement coverage has gaps. The digest system already structures data by domain, but the planner doesn't leverage this structure.

## What Changes

- **Replace single-call decompose with 3-phase domain-parallel pipeline:**
  - **Phase 1 (Planning Brief):** Single opus call that reads all domain summaries and produces a JSON brief — domain priorities, resource ownership map, cross-cutting changes, phasing strategy.
  - **Phase 2 (Domain Decompose):** N parallel opus calls (one per domain), each receiving only its domain's requirements + the planning brief + conventions. Produces per-domain change lists.
  - **Phase 3 (Merge & Resolve):** Single opus call that takes all domain plans, resolves cross-domain dependencies, detects conflicts, assigns phases, validates coverage, and outputs the final `orchestration-plan.json`.
- **Unified flow:** Always runs 3 phases, even for single-domain projects (Phase 3 becomes trivial). No fallback to single-call mode.
- **Selective replan:** Replan triggers only re-run the phases needed — domain-level failure re-runs Phase 2 for that domain + Phase 3; E2E failure re-runs Phase 3 only; spec change re-runs all 3.

## Capabilities

### New Capabilities
- **domain-parallel-decompose**: 3-phase domain-parallel planning pipeline with planning brief, per-domain decompose, and merge/resolve.

### Modified Capabilities
_None — this replaces the internal planning implementation without changing external interfaces._

## Impact

- **lib/set_orch/planner.py**: `run_planning_pipeline()` refactored into 3 phases. New functions: `build_planning_brief()`, `decompose_domain()`, `merge_domain_plans()`. Parallel execution via threading for Phase 2.
- **lib/set_orch/templates.py**: New prompt templates for brief, domain-decompose, and merge phases.
- **lib/set_orch/engine.py**: Minimal — `_auto_replan_cycle()` updated to use selective phase re-runs based on trigger type.
- **External interface unchanged**: `orchestration-plan.json` format stays the same. Engine, dispatcher, verifier see no difference.
- **All models opus**: No sonnet — opus for all 3 phases.
