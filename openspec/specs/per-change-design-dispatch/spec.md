# Spec: Per-Change Design Dispatch

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Dispatcher generates per-change `design.md` file at dispatch time
- Scope-matched extraction from design-brief.md using page name keywords
- Agent input.md references the per-change design.md file
- Abstract dispatch mechanism in core (Layer 1), customizable by profile (Layer 2)

### Out of scope
- Modifying the verify/review gate design compliance checks
- Changing how design tokens are extracted from design-system.md
- Planner-level design token embedding in scope text (existing behavior unchanged)

## Requirements

### Requirement: Generate per-change design file at dispatch

The dispatcher SHALL generate a `design.md` file in each change's directory containing scope-matched design context extracted from project design files. This file SHALL contain design tokens (always) and matched page visual descriptions (scope-filtered).

#### Scenario: Dispatch with design-brief.md present
- **WHEN** `dispatch_single_change()` is called
- **AND** `design-brief.md` exists in the project (checked at standard paths: `docs/design-brief.md`, `design-brief.md`)
- **THEN** the dispatcher reads `design-brief.md` and matches `## Page: <name>` sections against the change scope
- **AND** writes `openspec/changes/<name>/design.md` with: Design Tokens (from design-system.md) + matched page sections (from design-brief.md) + Components (from design-system.md)
- **AND** no line limit is applied to the per-change file

#### Scenario: Dispatch without design-brief.md (backwards compatible)
- **WHEN** `dispatch_single_change()` is called
- **AND** no `design-brief.md` exists
- **THEN** the existing inline Design Context injection in input.md continues to work unchanged
- **AND** design-system.md and design-snapshot.md fallback chain is preserved

#### Scenario: Input.md references per-change design file
- **WHEN** a per-change `design.md` file has been generated
- **THEN** the agent's `input.md` contains a `## Design Context` section with:
  - Inline Design Tokens (colors, fonts, spacing — always present for CSS variable setup)
  - Instruction: "Read `design.md` in this change directory for detailed visual specifications of your pages"
- **AND** the full page descriptions are NOT duplicated inline in input.md

### Requirement: Page matching uses precise page-name keywords

The scope-to-page matching SHALL use page names and specific aliases rather than generic word matching to avoid false positives.

#### Scenario: Precise matching avoids over-matching
- **WHEN** a change scope contains "product reviews rating" 
- **THEN** it SHALL NOT match "AdminProducts" page (the word "product" alone is not sufficient)
- **AND** it SHALL match pages whose name or aliases are specifically relevant (e.g., "ProductDetail" if "product detail" appears in scope)

#### Scenario: Page name is primary match key
- **WHEN** a `## Page: ProductCatalog` section exists in design-brief.md
- **AND** the scope contains "catalog" or "productcatalog"
- **THEN** the ProductCatalog section is included in the per-change design.md

#### Scenario: Aliases provide additional matching
- **WHEN** a page has defined aliases (e.g., Home → "homepage", "hero banner", "featured coffees")
- **AND** the scope contains one of these aliases as a phrase
- **THEN** the page section is included in the per-change design.md

### Requirement: Abstract dispatch mechanism supports profile customization

The per-change design file generation SHALL be implemented as an abstract mechanism in core (Layer 1) that profiles (Layer 2) can customize.

#### Scenario: Core provides default matching
- **WHEN** no profile override exists
- **THEN** the core dispatcher uses case-insensitive page-name and alias substring matching against scope text

#### Scenario: Profile can override matching logic
- **WHEN** a project profile (e.g., WebProjectType) implements `design_page_aliases()` 
- **THEN** the dispatcher uses the profile's page-to-alias mapping instead of the default
- **AND** the profile can define domain-specific aliases (e.g., "kavek" → "ProductCatalog" for Hungarian routes)
