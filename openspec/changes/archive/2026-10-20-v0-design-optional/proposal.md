## Why

The design-fidelity gate registers unconditionally for all web projects, even those that don't use the v0 design pipeline. When `v0-export/` is absent, the gate now correctly skips at runtime (fix: 709011b9), but it still appears in pipeline logs, gate status, and cache config — unnecessary noise for operators. There's also no explicit config switch to disable the v0 pipeline; optionality is implicit via file presence, which is fragile and undocumented.

## What Changes

- **Conditional gate registration**: `WebProjectType.register_gates()` checks `detect_design_source()` at registration time. When the project has no v0 source, the `design-fidelity` gate is not added to the pipeline at all — no runtime skip, no log noise, no cache entry.
- **Explicit `design_pipeline` config**: New optional field in orchestration config (`design_pipeline: v0 | none`) that overrides auto-detection. When set to `none`, the gate is not registered and dispatch skips v0-export symlink creation regardless of whether `v0-export/` exists on disk.
- **Profile-level `has_design_pipeline()` method**: Single source of truth combining auto-detection (`v0-export/` presence) with explicit config override. Used by gate registration, dispatcher, and planner.

## Capabilities

### New Capabilities

_None — this change refactors existing behavior, no new capability spec needed._

### Modified Capabilities

- `design-fidelity-gate`: Gate registration becomes conditional on design pipeline availability via `has_design_pipeline()`.
- `gate-profiles`: Adds `design_pipeline` config field to orchestration directives; `"auto"` (default) auto-detects, `"none"` disables.

## Impact

- **Module** (`modules/web/set_project_web/project_type.py`): `register_gates()` conditionally includes design-fidelity; new `has_design_pipeline()` method.
- **Module** (`modules/web/set_project_web/v0_fidelity_gate.py`): Runtime skip logic stays as defense-in-depth (already committed).
- **Core** (`lib/set_orch/profile_types.py`): `has_design_pipeline()` added to `ProjectType` ABC with default `False`.
- **Core** (`lib/set_orch/dispatcher.py`): Uses `has_design_pipeline()` instead of inline `detect_design_source() != "none"` check.
- **Config** (`lib/set_orch/config.py`): `design_pipeline` added to directive defaults as `"auto"`.
- **Tests**: Coverage for conditional registration, config override, and the existing runtime skip.
- **No breaking changes**: Default behavior (`"auto"`) preserves current auto-detection. Projects with `v0-export/` continue working unchanged.
