# Design: planner-python-hardening

## Context

The planner pipeline (`planner.py` + `templates.py`) builds a prompt with ~200 lines of rules, sends it to Claude, parses the JSON response, and validates it. Currently validation catches structural issues (JSON format, dependency graph, REQ coverage) but lets through soft constraint violations (too many changes, L complexity, wrong model, oversized scope). Web-specific heuristics are embedded in `_PLANNING_RULES_CORE` — a core string — instead of living in the web module.

## Core Principle: Python Frame, LLM Content

Python validates every enforceable constraint **after** the LLM responds. The LLM plans freely within the frame — deciding change structure, scope text, dependency edges, requirement distribution. But the frame is non-negotiable:

| Constraint | Current | After |
|-----------|---------|-------|
| Change count ≤ max_target | Prompt only | Hard error in `validate_plan()` |
| Complexity ∈ {S, M} | Prompt only | Hard error in `validate_plan()` |
| Model ∈ {opus, sonnet} | Prompt only | Hard error in `validate_plan()` |
| Scope ≤ 2000 chars | Warning only | Hard error in `validate_plan()` |
| Web cross-cutting files | Hardcoded in core | From `profile.cross_cutting_files()` |
| Web planning heuristics | Hardcoded in core | From `profile.planning_rules()` |

On validation failure: the planner retries the LLM call with the error message appended to the prompt (existing retry mechanism in `run_planning_pipeline()`).

## Goals / Non-Goals

**Goals:**
- Hard Python validation for change count, complexity, model, scope length
- Web-specific planning rules moved to profile system
- Profile ABC extended with `planning_rules()` and `cross_cutting_files()`
- Core `_PLANNING_RULES_CORE` contains only universal rules

**Non-Goals:**
- Changing the LLM prompt structure or planning strategy
- Adding new planning phases or domain-parallel logic
- Modifying the digest or dispatch pipeline

## Decisions

### D1: Hard errors with retry, not rejection

**Choice:** Validation failures trigger LLM retry with error context, not immediate pipeline failure.

**Alternative:** Fail the pipeline and require human intervention.

**Why:** The LLM usually fixes constraint violations on retry when told specifically what failed. Rejecting the whole plan for `complexity: "L"` when the LLM can split it in one more call would waste the entire planning investment. The existing retry loop in `run_planning_pipeline()` already handles this pattern.

### D2: Profile methods return strings/lists, not prompt fragments

**Choice:** `planning_rules() -> str` returns plain rule text, `cross_cutting_files() -> list[str]` returns file paths. `templates.py` formats them into the prompt.

**Alternative:** Profile returns formatted prompt sections.

**Why:** Prompt formatting is templates.py's responsibility. Modules should provide domain knowledge, not prompt engineering. This matches existing patterns (`e2e_test_methodology()` returns plain text, templates.py wraps it).

### D3: cross_cutting_files() replaces hardcoded list

**Choice:** Move `CROSS_CUTTING_FILES = ["layout.tsx", "middleware.ts", ...]` from `_assign_cross_cutting_ownership()` to `profile.cross_cutting_files()`.

**Alternative:** Keep hardcoded list, add profile override.

**Why:** The current list is 100% web-specific. A dungeon-builder plugin has no `layout.tsx`. The profile method is the clean extension point. `_assign_cross_cutting_ownership()` calls the profile to get the list.

## Risks / Trade-offs

**[Risk] Hard validation causes planning loop** → Mitigation: Max 3 retries (existing limit). After 3 failures, log error with specifics and proceed with best-effort plan.

**[Risk] Web rules removal breaks existing behavior** → Mitigation: The rules move to `WebProjectType.planning_rules()` which is called for web projects. Non-web projects simply don't get web rules (which is correct — they shouldn't have had them before).

## Open Questions

None.
