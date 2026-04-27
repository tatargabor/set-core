# Spec: v0 Design Source (delta)

## ADDED Requirements

**IN SCOPE:** web module's design-source slicing for v0 exports; scope-keyword matching against `design-manifest.yaml`; copying matched v0 files into per-change `design-source/`; token extraction from synced `globals.css`; agent-facing design context construction.

**OUT OF SCOPE:** generic Layer 1 dispatch context (covered by `design-dispatch-context` and `design-dispatch-injection` deltas); visual fidelity verification (covered by `design-fidelity-gate`); manifest generation (covered by `v0-export-import`); AI-vision-based scope matching (deferred to v2).

### Requirement: WebProjectType implements design-source provider

The `WebProjectType` in `modules/web/set_project_web/project_type.py` SHALL implement the design-source provider interface defined by `ProjectType` ABC.

#### Scenario: WebProjectType.detect_design_source returns v0 when v0-export exists
- **GIVEN** the project root contains `v0-export/` directory
- **WHEN** `WebProjectType().detect_design_source(project_path)` is called
- **THEN** it returns the string `"v0"`

#### Scenario: WebProjectType.detect_design_source returns none otherwise
- **GIVEN** the project root has no `v0-export/` directory
- **WHEN** `detect_design_source()` is called
- **THEN** it returns the string `"none"`

### Requirement: Scope-keyword matching against manifest

The web module SHALL match a change's scope text against `design-manifest.yaml` route entries using keyword overlap.

#### Scenario: Match by scope_keyword substring
- **GIVEN** the manifest contains a route `/kavek` with `scope_keywords: [catalog, kavek, products, coffees]`
- **AND** a change scope mentions "implement product catalog page with filters"
- **WHEN** scope matching runs
- **THEN** the route `/kavek` is selected (substring match on "catalog" or "products")
- **AND** the route's `files` and `component_deps` are added to the design-source slice

#### Scenario: Multiple routes match
- **GIVEN** a change scope spans "homepage, header, footer"
- **WHEN** scope matching runs
- **THEN** all routes whose `scope_keywords` overlap (e.g. `/` and the shared header/footer) are selected
- **AND** their files combine into a deduplicated design-source slice

#### Scenario: No route matches when change scope is non-UI (graceful)
- **WHEN** no manifest route's `scope_keywords` match the scope text
- **AND** the change scope contains NO UI-indicating keywords (heuristic: scope text lacks "page", "view", "component", "screen", "render", "layout", "form", "modal", "dialog", or any manifest route segment)
- **THEN** the design-source slice contains only the `shared:` files (header, footer, ui/, layout, globals.css)
- **AND** an INFO is logged: `"No design-manifest route matched scope: <scope>; using shared-only (change appears non-UI)"`

#### Scenario: No route matches when change scope IS UI-bound (HARD FAIL)
- **WHEN** no manifest route's `scope_keywords` match the scope text
- **AND** the change scope DOES contain UI-indicating keywords
- **THEN** the slice provider raises `NoMatchingRouteError`
- **AND** the dispatcher fails the change with reason `design-route-unmatched`
- **AND** the error message names the scope text + the keywords that suggested UI binding + a remediation: "Either: (1) add a `design_routes: [...]` field to this change in the orchestration plan to bind explicitly, (2) update manifest scope_keywords for the relevant route, or (3) decompose this UI work into changes that match existing routes"
- **RATIONALE** (per design D8): UI changes that don't match any design route are planning bugs, not graceful-fallback cases. Silent shared-only fallback would dispatch the agent with no page-level design guidance, producing wrong output.

### Requirement: Per-change design-source directory population

The web module SHALL copy scope-matched v0 files into the dispatcher-provided `dest_dir` (typically `openspec/changes/<change_name>/design-source/`) preserving the v0-export directory layout. The `dest_dir` and `change_name` are passed by the dispatcher; the web module SHALL NOT compute the path itself.

#### Scenario: Copy matched files preserving structure
- **GIVEN** the slice contains `v0-export/app/kavek/page.tsx` and `v0-export/components/product-card.tsx`
- **AND** the dispatcher computes `dest_dir = openspec/changes/<change_name>/design-source/`
- **WHEN** `WebProjectType().copy_design_source_slice(change_name, scope, dest_dir)` runs
- **THEN** `<dest_dir>/app/kavek/page.tsx` and `<dest_dir>/components/product-card.tsx` exist
- **AND** files are byte-identical to the v0-export originals

#### Scenario: Shared files always included
- **WHEN** any per-change design-source is populated
- **THEN** all `shared:` glob matches from the manifest are copied (header, footer, ui/, layout.tsx, globals.css)
- **AND** missing shared files are reported as ERROR (manifest is broken)

#### Scenario: Stale design-source removed before re-population
- **GIVEN** the `dest_dir` already exists from a previous dispatch
- **WHEN** per-change population runs again (e.g. on retry)
- **THEN** the existing directory is removed first
- **AND** only files from the current scope match are present after population

### Requirement: Token extraction from synced globals.css

The web module SHALL extract design tokens from `<project>/shadcn/globals.css` (or wherever the runner deploys it) for inclusion in the agent's dispatch context as a quick-reference summary.

#### Scenario: Extract CSS custom properties
- **WHEN** token extraction runs
- **THEN** all `:root { --foo: ... }` and `.dark { --foo: ... }` declarations are parsed
- **AND** returned as a structured dict {token_name → value, mode}

#### Scenario: globals.css missing
- **WHEN** the file does not exist at the expected path
- **THEN** an empty token set is returned
- **AND** a WARNING is logged

### Requirement: Agent dispatch context references design-source

The web module's `get_design_dispatch_context(change_name, scope, project_path)` SHALL return a markdown block instructing the agent to read `openspec/changes/<change_name>/design-source/` as the design source of truth. The `change_name` parameter MUST be present so the block can reference the exact change directory.

#### Scenario: Context block structure
- **WHEN** dispatch context is built for a change with v0 design source
- **THEN** the returned block contains:
  - A header pointing to `openspec/changes/<change_name>/design-source/` directory (using the `change_name` parameter, not a placeholder)
  - A list of the included v0 files (route + shared)
  - A "Design Tokens" section with the parsed globals.css values
  - A reference to the design-bridge.md rule for the refactor policy

#### Scenario: Context size budget
- **WHEN** the context block is built
- **THEN** it SHALL NOT exceed 200 lines (token extraction + file list — actual TSX content stays in design-source files, not embedded in the context block)
