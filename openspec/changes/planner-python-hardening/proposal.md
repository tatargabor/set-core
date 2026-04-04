# Change: planner-python-hardening

## Why

The planner pipeline delegates too many enforceable constraints to LLM prompt guidance. From craftbrew-run20 analysis: the LLM generated fewer changes than optimal for a large project because the "target 6 changes" rule is only in the prompt — Python doesn't enforce it. Similarly, complexity="L" is forbidden in the prompt but not validated, and web-specific planning rules (layout.tsx serialization, CRUD test checklists, schema-before-data ordering) are hardcoded in `templates.py` core rules instead of living in the web module.

**Core principle: Python enforces the frame, LLM plans within it.** If a constraint can be expressed as a Python check, it must not rely on LLM compliance.

## What Changes

### 1. Python hard validation for LLM plan output

Add to `validate_plan()`:
- **Change count**: `len(changes) <= max_change_target` → hard error (not just prompt guidance)
- **Complexity**: `complexity not in ("S", "M")` → hard error (L is forbidden)
- **Model assignment**: `model not in ("opus", "sonnet")` → hard error
- **Scope length**: `len(scope) > 2000` → hard error (not just warning)

### 2. Web-specific planning rules to profile

Move from `_PLANNING_RULES_CORE` in `templates.py` to `WebProjectType`:
- `"schema/migration before data-layer"` → `planning_rules()`
- Cross-cutting file list (`layout.tsx, middleware.ts, tailwind.config`) → `cross_cutting_files()`
- CRUD test requirements → `planning_rules()`
- i18n namespace convention → `planning_rules()`

### 3. Profile ABC extension

Add to `ProjectType` in `profile_types.py`:
- `planning_rules() -> str` — module-specific planning rules injected into planner prompt. Default: empty.
- `cross_cutting_files() -> list[str]` — files that need serialization if touched by multiple changes. Default: empty.

### 4. Templates integration

`_get_planning_rules()` in `templates.py` calls `profile.planning_rules()` and appends module-specific rules after core rules. `_assign_cross_cutting_ownership()` in `planner.py` calls `profile.cross_cutting_files()` instead of using a hardcoded list. Core rules stay in `_PLANNING_RULES_CORE`, module rules are appended.

## Capabilities

### New Capabilities
- `planner-validation-hardening` — Python hard checks on plan output

### Modified Capabilities
- None (existing planning specs describe the prompt structure, not validation)

## Impact

- `lib/set_orch/planner.py` — `validate_plan()` gains 4 hard checks
- `lib/set_orch/profile_types.py` — `ProjectType` ABC gains `planning_rules()`, `cross_cutting_files()`
- `lib/set_orch/templates.py` — `_PLANNING_RULES_CORE` trimmed, `render_planning_prompt()` calls profile
- `modules/web/set_project_web/project_type.py` — implements `planning_rules()`, `cross_cutting_files()`
