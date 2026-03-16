## Why

The current pipeline has a structural gap between specification and implementation verification. Agents can hallucinate features not in the spec (overshoot) and miss specified requirements (undershoot) without reliable detection. The verify gate uses keyword-based heuristics and one-directional checking (spec→code) but lacks backward checking (code→spec). Task files don't reference which spec requirements they implement, breaking traceability. The soft-pass logic in the verify gate auto-passes when spec verification times out, silently skipping compliance checks. These gaps mean spec fidelity depends on agent discipline rather than structural guarantees.

## What Changes

- **Spec scope boundaries**: Add explicit IN SCOPE / OUT OF SCOPE sections to the spec artifact template, giving agents and verifiers a clear "fence" for what should and should not be implemented
- **Task-requirement traceability**: Modify the ff-change skill to generate tasks with requirement ID references and a traceability matrix, enabling mechanical verification that every requirement has at least one task
- **Bidirectional verify gate**: Enhance the verify-change skill with forward checking (every spec requirement has implementation) AND backward/overshoot checking (every new route, endpoint, component, or export maps back to a spec requirement)
- **Acceptance test skeleton generation**: Add a step in the ff-change skill that generates testable acceptance criteria from WHEN/THEN scenarios, which the apply agent must satisfy
- **Soft-pass fix**: Remove the permissive soft-pass logic that auto-passes spec verification when the sentinel string is missing and all other gates passed
- **Plan completeness check**: Add reverse requirement coverage validation to `validate_plan()` — every digest requirement must be assigned to at least one change or explicitly deferred, catching missing requirements at plan time (30-second re-plan) instead of at verify time (1-3 hour retry)

## Capabilities

### New Capabilities
- `scope-boundary`: IN SCOPE / OUT OF SCOPE section in spec template, with enforcement in verify skill
- `task-traceability`: Requirement ID linking in tasks.md with traceability matrix generation
- `overshoot-detection`: Backward verification that implementation doesn't exceed spec scope
- `acceptance-skeleton`: WHEN/THEN scenario extraction into testable acceptance criteria
- `plan-completeness`: Reverse requirement coverage in validate_plan() with deferred_requirements support

### Modified Capabilities
- `verify-gate`: Fix soft-pass logic, add bidirectional checking pipeline, add scope boundary enforcement
- `verify-review`: Add overshoot detection to the LLM code review prompt (flag new routes/endpoints/components not in spec)

## Impact

- **openspec CLI / spec template**: Spec artifact template gains IN SCOPE / OUT OF SCOPE sections
- **ff-change skill (SKILL.md)**: Task generation instructions updated for requirement traceability and acceptance skeleton
- **verify-change skill (SKILL.md)**: New verification dimensions — overshoot detection and scope boundary check
- **verifier.py**: Soft-pass logic fix in `handle_change_done()`, overshoot detection in review prompt builder
- **planner.py**: Plan completeness check in `validate_plan()`, deferred_requirements support in plan schema
- **decompose skill**: Updated prompt to require explicit deferred_requirements for uncovered requirements
- **No breaking changes**: All additions are backward-compatible — existing changes without scope boundaries or traceability gracefully degrade to current behavior
