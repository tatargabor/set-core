## Context

The v0 design pipeline (v0-export/, scaffold.yaml, design-fidelity gate) is used by web projects that import a v0 design source. Many web projects don't use this pipeline at all. Currently, the design-fidelity gate is registered unconditionally by `WebProjectType.register_gates()` for all web projects. At runtime it skips when no v0 source exists (fix 709011b9), but it still occupies a slot in the gate pipeline, appears in logs, and has cache config entries.

The dispatcher already conditionally deploys v0-export via `detect_design_source()`, and the planner gracefully degrades when no design files exist. The gate registration is the last unconditional coupling point.

## Goals / Non-Goals

**Goals:**
- Gate registration conditional on design source availability
- Single `has_design_pipeline()` method as the source of truth
- Explicit `design_pipeline` directive for operator override
- Runtime skip in v0_fidelity_gate stays as defense-in-depth

**Non-Goals:**
- Refactoring the v0 pipeline internals (scaffold.yaml parsing, v0-export structure)
- Making other design-related features conditional (design-bridge rule, design-sync)
- Adding new design source types

## Decisions

### D1: `has_design_pipeline()` on ProjectType ABC

Add `has_design_pipeline(project_path: Path) -> bool` to `ProjectType` in `profile_types.py`. Default returns `False`. `WebProjectType` overrides: returns `True` when `detect_design_source() != "none"`.

**Why over alternative (check at each call site):** Centralizes the decision. The dispatcher, gate registration, and planner can all call one method instead of each having their own `detect_design_source() != "none"` check.

### D2: `design_pipeline` directive with `"auto"` default

Add `"design_pipeline": "auto"` to `DIRECTIVE_DEFAULTS` in `config.py`. Valid values: `"auto"`, `"none"`.

- `"auto"` (default): `has_design_pipeline()` delegates to `detect_design_source()` — current behavior preserved.
- `"none"`: `has_design_pipeline()` returns `False` unconditionally, even if `v0-export/` exists on disk.

**Why not a boolean:** `"auto"` vs `"none"` is clearer than `True`/`False` — a boolean doesn't communicate that detection happens. Future values like `"v0"` (force v0 even without v0-export/) are possible but not needed now.

### D3: Conditional gate registration via `register_gates()`

`WebProjectType.register_gates()` receives `project_path` (already available on `self` via profile initialization). When `has_design_pipeline()` returns `False`, the `design-fidelity` GateDefinition is simply not included in the returned list.

**Why not gate_overrides:** `gate_overrides` sets the gate to `"skip"` mode — the gate entry still exists in the pipeline, gets logged, consumes a cache slot. Not registering it at all is cleaner for projects that never use v0.

### D4: Runtime skip stays as defense-in-depth

The runtime skip in `v0_fidelity_gate.py:478-491` stays unchanged. If someone manually adds the gate via gate_overrides or a future code path registers it, the runtime check prevents the FAIL-with-no-remediation scenario.

## Risks / Trade-offs

- **[Risk] Profile instantiation needs project_path at register_gates() time** → Already available: `WebProjectType.__init__` receives project config including path. Verify during implementation.
- **[Risk] Directive not available at profile load time** → `has_design_pipeline()` needs to read directives. The profile has access to the orchestration config via `self.config`. If not, pass directives explicitly.

## Migration Plan

1. Add `has_design_pipeline()` to ABC and WebProjectType
2. Add `design_pipeline` to DIRECTIVE_DEFAULTS
3. Wire `has_design_pipeline()` to read the directive
4. Make `register_gates()` conditional
5. Replace inline `detect_design_source() != "none"` in dispatcher with `has_design_pipeline()`

No rollback needed — `"auto"` default preserves current behavior exactly.

## Open Questions

None — scope is narrow and all integration points are verified.
