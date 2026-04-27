# Spec: Decompose Design Binding (delta)

## ADDED Requirements

**IN SCOPE:** decompose skill awareness of `design-manifest.yaml`; explicit per-change route binding (`design_routes` field) in orchestration plan; manifest coverage validation (every route → exactly 1 change OR explicitly deferred); dispatcher prefers explicit binding over scope-keyword fuzzy matching.

**OUT OF SCOPE:** automatic generation of changes from manifest alone (decompose still consumes a spec); decomposing the v0 design itself (v0 is the input, not the input to decompose); LLM-based route → spec-item matching (v1 uses heuristic matching authored by the planner agent).

### Requirement: Decompose skill reads design-manifest.yaml

When generating an orchestration plan, the decompose skill SHALL read `<scaffold>/docs/design-manifest.yaml` (or `<project>/docs/design-manifest.yaml` if running in a deployed project) and use route entries to inform plan generation. If no manifest exists, decompose SHALL proceed without it (graceful degradation).

#### Scenario: Decompose with v0 manifest present
- **WHEN** the decompose skill runs in a project where `docs/design-manifest.yaml` exists
- **THEN** the skill reads the manifest before generating the plan
- **AND** treats each route entry as a candidate "change unit" (one route per change OR multiple routes grouped into a feature change)
- **AND** uses `scope_keywords` from the manifest to inform the change's `scope` text so dispatch-time matching succeeds

#### Scenario: Decompose without manifest (graceful)
- **WHEN** the decompose skill runs in a project where no `design-manifest.yaml` exists
- **THEN** the skill falls back to its existing behavior (spec-driven decomposition with no design awareness)
- **AND** logs INFO: `"No design-manifest.yaml found — proceeding without design-route binding."`

### Requirement: Per-change explicit route binding

The orchestration plan output (`orchestration-plan.json`) SHALL support a new per-change field `design_routes: list[str]` that explicitly binds the change to one or more manifest route paths. This is the AUTHORITATIVE source for design-source slicing — when set, it overrides scope-keyword fuzzy matching.

#### Scenario: Plan includes design_routes per change
- **WHEN** the decompose skill generates a plan AND a manifest is present
- **THEN** each change in `changes[]` SHALL have a `design_routes` field listing the manifest route paths the change implements
- **AND** the field is a list (a change can implement multiple routes, e.g. catalog change implements both `/kavek` and `/kavek/[slug]`)
- **AND** changes that don't touch UI MAY omit the field (or set it to empty list)

#### Scenario: Field schema example
```json
{
  "name": "implement-product-catalog",
  "scope": "Implement product listing and filtering pages...",
  "design_routes": ["/kavek", "/kavek/[slug]"],
  "complexity": "M",
  "depends_on": ["foundational-shared-layout"],
  ...
}
```

#### Scenario: Backward compatibility
- **GIVEN** an older orchestration plan was generated without `design_routes` field
- **WHEN** the dispatcher reads it
- **THEN** the dispatcher falls back to scope-keyword matching (existing behavior)
- **AND** does NOT error on the missing field

### Requirement: Manifest coverage validation

The decompose skill SHALL validate that every route in `design-manifest.yaml` is accounted for by exactly one change OR explicitly deferred. Silent omission is a planning error, the same way unaccounted requirements are.

**Layer separation**: the validation logic itself MUST live in the web module (`modules/web/`), NOT in `lib/set_orch/`. The Layer 1 `validate_plan()` calls into a profile method (`profile.validate_plan_design_coverage(plan, project_path) -> list[str]`) that returns a list of violation messages. The default ABC implementation returns `[]` (no design awareness — backward compatible). `WebProjectType` overrides it to read `<project_path>/docs/design-manifest.yaml` and perform the coverage check. This keeps `lib/set_orch/planner.py` agnostic of v0/manifest concepts.

#### Scenario: Coverage check at plan generation (opt-in trigger)
- **WHEN** the decompose skill finalizes the plan
- **AND** the plan contains AT LEAST ONE non-empty `design_routes` field on any change OR a non-empty `deferred_design_routes[]` array (this is the OPT-IN signal that the planner is design-aware)
- **THEN** coverage enforcement triggers:
  - Compute the set of all manifest route paths
  - The set of all `design_routes` values across all changes
  - The set of all routes listed in `deferred_design_routes[]` (each entry has `route` + `reason` fields)
  - Every manifest route MUST appear in EXACTLY ONE of: a change's `design_routes`, or `deferred_design_routes[]`

#### Scenario: Backward compatibility — old plans skip coverage
- **GIVEN** a plan was generated before the manifest-aware decompose update (no `design_routes` on any change AND no `deferred_design_routes[]` array)
- **WHEN** `validate_plan_design_coverage` runs against this plan
- **THEN** the check is SKIPPED (returns `[]` — no violations) regardless of manifest contents
- **AND** an INFO log records: `"Plan has no design_routes fields — coverage check skipped (legacy plan)."`
- **AND** the dispatcher falls back to scope_keyword matching (existing behavior preserved)
- **RATIONALE**: requiring old plans to suddenly account for every manifest route would break every project that adds a manifest after their plan was generated. Coverage is opt-in via the planner emitting the new fields.

#### Scenario: Mixed plan triggers coverage (opt-in is per-plan, not per-change)
- **GIVEN** a plan has `design_routes: ["/kavek"]` on one change AND no `design_routes` field on others
- **WHEN** coverage check runs
- **THEN** it triggers (the plan is design-aware) and ALL manifest routes must be accounted
- **AND** changes without `design_routes` contribute 0 routes to coverage; their routes must be claimed by other changes or deferred
- **AND** this prevents accidental partial-binding (planner must be intentional — bind all UI changes or none)

#### Scenario: Unaccounted route is a planning error
- **WHEN** a manifest route is in NEITHER any change nor `deferred_design_routes`
- **THEN** the decompose skill emits an ERROR: `"Manifest route /<path> is not assigned to any change and not deferred. Either add it to a change's design_routes[] or list it in deferred_design_routes[] with a reason."`
- **AND** the plan is INVALID (validate_plan rejects it)
- **AND** dispatch is blocked

#### Scenario: Deferred routes are explicit
- **WHEN** a route is intentionally not implemented in this phase (e.g. /admin/* deferred to phase 2)
- **THEN** the plan SHALL include it in `deferred_design_routes`:
  ```json
  "deferred_design_routes": [
    {"route": "/admin/visszakuldesek", "reason": "Returns workflow scheduled for phase 2"}
  ]
  ```
- **AND** the dispatcher SHALL skip these routes when computing slices

#### Scenario: Multi-change route assignment is an error
- **GIVEN** route `/kavek` is in both `change-A.design_routes` and `change-B.design_routes`
- **WHEN** the coverage check runs
- **THEN** an ERROR is emitted: `"Route /kavek assigned to multiple changes (change-A, change-B). Each route must belong to exactly one change."`
- **AND** the plan is INVALID

### Requirement: Dispatcher prefers explicit design_routes over scope_keyword matching

When the dispatcher builds the per-change design-source slice, it SHALL prefer the change's explicit `design_routes` field (if present and non-empty). Scope-keyword fuzzy matching is the fallback for changes without explicit binding (typically older plans or non-UI changes that want shared files only).

#### Scenario: Explicit design_routes used
- **GIVEN** the change's plan entry has `design_routes: ["/kavek", "/kavek/[slug]"]`
- **WHEN** the dispatcher calls `profile.copy_design_source_slice(change_name, scope, dest)`
- **THEN** the implementation looks up those EXACT route paths in the manifest
- **AND** copies the matched routes' files + `shared:` files into `dest/`
- **AND** does NOT consult `scope_keywords`

#### Scenario: Empty design_routes falls back to keyword matching
- **GIVEN** the change's plan entry has `design_routes: []` or omits the field
- **WHEN** the dispatcher runs
- **THEN** the dispatcher falls back to the existing scope-keyword fuzzy matcher (per `v0-design-source` capability)
- **AND** an INFO log notes: `"<change_name> has no explicit design_routes; using scope-keyword fallback."`

#### Scenario: Explicit route does not exist in manifest
- **WHEN** a change's `design_routes` contains a route that does not exist in `design-manifest.yaml`
- **THEN** the dispatcher emits an ERROR for that change: `"design_route <path> not found in manifest. Plan is stale or manifest changed; regenerate plan."`
- **AND** dispatch is blocked for that change (other changes may proceed)

### Requirement: Decompose skill instructs planner agent on design awareness

The decompose skill (`SKILL.md`) SHALL be updated to direct its agent to:
1. Read `docs/design-manifest.yaml` early in the planning phase (after spec read, before plan generation)
2. Map each manifest route to the spec item that implements it (1:1 or many:1)
3. Set `design_routes` on each change appropriately
4. Validate coverage (every route accounted for) before writing the plan
5. Treat manifest as the authoritative inventory of UI surfaces — if the spec mentions a UI feature not in the manifest, that's a `design_gap` ambiguity

#### Scenario: Skill reads manifest as part of project context discovery
- **WHEN** the decompose skill reaches Step 2 ("Read project context")
- **THEN** the agent ALSO reads `docs/design-manifest.yaml` (in addition to existing project-type, project-knowledge, requirements, orchestration files)

#### Scenario: Skill maps routes to spec items
- **WHEN** the agent generates the plan
- **THEN** the plan includes a `design_route_map` debug section (in plan reasoning) showing which manifest routes were mapped to which spec items
- **AND** any unmapped routes get listed in `deferred_design_routes` with the agent's reasoning

#### Scenario: Skill flags spec ↔ manifest gaps
- **WHEN** the spec describes a UI feature with no corresponding manifest route (e.g., spec says "user can browse press releases at /sajto" but manifest has no /sajto)
- **THEN** the plan's `reasoning` field flags this as a `design_gap`: "Spec mentions /sajto but no v0 design exists. Either: regenerate v0 with this page added, OR remove this feature from the spec, OR proceed without design and accept fidelity-gate skip for this route."

#### Scenario: Skill flags manifest ↔ spec gaps
- **WHEN** a manifest route has no corresponding spec item (v0 designed a page the spec doesn't describe)
- **THEN** the plan's `reasoning` flags it: "Manifest contains /kapcsolat but spec does not mention it. Auto-deferred. Add to spec or remove from manifest if not needed."
- **AND** the route goes into `deferred_design_routes` with reason `"manifest-only — no spec item; auto-deferred"`
