## ADDED Requirements

### Requirement: skip_test guarded by scope file-path content
The decomposition agent (API or agent-based) SHALL NOT set `skip_test=true` on a change whose `scope` paragraph includes any file path with a substring from the guard list: `server/`, `actions/`, `handlers/`, `services/`, `validators/`, `/lib/business/`, `/api/` (route handlers). The guard SHALL be implemented as a deterministic path-substring scan — no natural-language or verb-association scanning.

Allowed use of `skip_test=true` is restricted to scopes whose file paths are all within: scaffolding dirs (new project layouts), `public/`, `messages/` (i18n catalogs), `prisma/` (migrations-only), `docs/`, or top-level config files (`*.config.*`, `*.json`, `*.yaml`, `*.toml`).

The planner prompt schema SHALL document this restriction so the agent-mode planner also respects it.

#### Scenario: Scope with validators rejects skip_test
- **WHEN** the decomposer proposes a change with `scope` containing `src/server/promotions/coupon-validator.ts`
- **AND** the proposed change has `skip_test=true`
- **THEN** the planner's validator SHALL reject the plan
- **AND** the agent SHALL revise and set `skip_test=false`

#### Scenario: Scaffolding-only scope allows skip_test
- **WHEN** the scope is `Initial directory structure: add tsconfig.json, .eslintrc.json, prettier.config.js`
- **AND** `skip_test=true`
- **THEN** the planner's validator SHALL accept

### Requirement: Size-estimate formula for change sizing
The decomposer SHALL compute an `estimated_loc` score for every proposed change using a profile-weighted formula and compare it to a configurable threshold. This replaces any prior hard cap on requirements/scenarios/file counts — those counts correlate poorly with actual implementation effort, whereas LOC-weighted file paths plus schema work plus ambiguity count correlate well.

The formula SHALL be:

```
estimated_loc(change) =
    Σ(loc_weight(path) for path in scope.file_paths)
    + len(models_added_or_modified) * schema_weight
    + len(resolved_ambiguities) * ambiguity_weight
```

Default weights (provided by `CoreProfile`, overridable per project-type):
- `schema_weight = 120` — Prisma/schema migration + downstream type impact
- `ambiguity_weight = 80` — each unresolved design decision surfaces extra work
- `loc_weight(path)` defaults to `150` for unknown paths

`ProjectType.loc_weights() -> dict[str, int]` SHALL declare per-pattern weights. Resolution: longest glob wins, then specificity tiebreaker. The web profile declares:
- `src/app/admin/**/page.tsx` → `350`
- `src/app/[locale]/**/page.tsx` → `200`
- `src/components/**/*.tsx` → `180`
- `src/server/**/*.ts` → `200`
- `tests/**/*.spec.ts` → `150`

The threshold `per_change_estimated_loc_threshold` (default `1500`) SHALL be configurable via orchestration directive.

#### Scenario: Small change under threshold passes through
- **WHEN** the agent proposes a change whose `estimated_loc` is `900`
- **AND** the threshold is `1500`
- **THEN** the planner SHALL emit it as-is with no split

#### Scenario: Large change triggers sibling split
- **WHEN** the agent proposes a change whose `estimated_loc` is `3760`
- **AND** the threshold is `1500`
- **THEN** the planner SHALL auto-split into ≥2 sibling changes

#### Scenario: Profile supplies web-specific weights
- **WHEN** the active profile is `WebProjectType` and the scope contains `src/app/admin/orders/page.tsx`
- **THEN** `loc_weight()` SHALL resolve the path to `350`
- **AND** an unknown path (e.g., `scripts/seed.ts`) SHALL fall back to `150`

### Requirement: Linked sibling split strategy
When a change exceeds the size threshold, the planner SHALL produce N sibling changes sharing the original base name and chained via `depends_on`. Siblings live in the SAME `phase` as the original.

Naming convention: `<base-name>-<group-label>-<N>` where:
- `base-name` is the original change name (e.g., `admin-operations`).
- `group-label` is a short kebab-case token describing the sibling's focus (e.g., `orders`, `dashboard`, `returns`), inferred from file-path commonalities or explicit scope sub-areas.
- `N` is the 1-based sequence number matching the `depends_on` order.

Example split of `admin-operations` (estimated_loc=3760):
- `admin-operations-orders-1` (depends_on: `[]`)
- `admin-operations-dashboard-2` (depends_on: `[admin-operations-orders-1]`)
- `admin-operations-returns-3` (depends_on: `[admin-operations-dashboard-2]`)

The chain SHALL enforce sequential execution so that shared scaffolding (admin shell, layout, shared components) lands in sibling 1 and later siblings inherit it.

Auto-split SHALL run during plan generation, BEFORE the plan is persisted to `orchestration-plan.json` and BEFORE `orchestration-state.json` is initialised from the plan. Consequently, the sibling names ARE the canonical names from the engine's point of view — no pre-split name ever appears in state or on disk, and the divergent-plan reconciliation path never sees a split as a "stale" change.

Splits SHALL be cohesive: the planner SHALL group the scope's file paths by directory prefix (first two path segments) or by explicit scope sub-headings before cutting. Each sibling SHALL carry its own subset of `requirements`, `also_affects_reqs`, `spec_files`, and `resolved_ambiguities`. The first sibling inherits the original `scope` preamble; subsequent siblings get a scope preamble generated from their own grouped content.

#### Scenario: admin-operations splits into 3 linked siblings
- **WHEN** a proposed `admin-operations` change has `estimated_loc=3760` covering 9 admin pages
- **THEN** the planner SHALL produce `admin-operations-orders-1`, `admin-operations-dashboard-2`, `admin-operations-returns-3`
- **AND** each sibling's `estimated_loc` SHALL be `≤ threshold * 1.1` (10% grace for cohesion — pure equal-split is not required)
- **AND** `admin-operations-orders-1.depends_on == []`
- **AND** `admin-operations-dashboard-2.depends_on == ["admin-operations-orders-1"]`
- **AND** `admin-operations-returns-3.depends_on == ["admin-operations-dashboard-2"]`
- **AND** all three siblings share `phase=2` (same as the original)

#### Scenario: promotions-engine splits by concern
- **WHEN** a proposed `promotions-engine` change has `estimated_loc=2000` covering server logic (coupon + gift-card + promo-day) AND 3 admin pages
- **THEN** the planner SHALL split by directory prefix: `promotions-engine-server-1` (server modules + cart UI) → `promotions-engine-admin-2` (3 admin pages)
- **AND** `promotions-engine-admin-2.depends_on == ["promotions-engine-server-1"]`

#### Scenario: Pre-split name never persists
- **WHEN** auto-split runs on `promotions-engine`
- **THEN** `orchestration-plan.json` SHALL contain `promotions-engine-server-1` and `promotions-engine-admin-2` but NOT `promotions-engine`
- **AND** no `change/promotions-engine` branch or `openspec/changes/promotions-engine/` dir SHALL ever be created

### Requirement: Content hints for gate selection
The decomposer SHALL populate a `touched_file_globs` field on each change — a list of glob patterns derived from the scope paragraph. This field is consumed by the content-aware gate selector (`per-change-gate-skip` spec delta). The globs SHALL include at minimum every explicit file path mentioned in the scope plus wildcard parents for each directory mentioned.

#### Scenario: Scope mentions UI files
- **WHEN** the scope contains `src/app/[locale]/(shop)/kosar/page.tsx` and `src/components/cart/cart-item.tsx`
- **THEN** `touched_file_globs` SHALL include `src/app/[locale]/(shop)/kosar/page.tsx`, `src/app/[locale]/(shop)/kosar/**`, `src/components/cart/cart-item.tsx`, `src/components/cart/**`

#### Scenario: Scope mentions only server files
- **WHEN** the scope contains `src/server/promotions/coupon-validator.ts`
- **THEN** `touched_file_globs` SHALL NOT include any UI-route glob
- **AND** SHALL include `src/server/promotions/coupon-validator.ts` and `src/server/promotions/**`
