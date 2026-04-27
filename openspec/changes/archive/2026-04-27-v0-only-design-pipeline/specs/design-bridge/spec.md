# Spec: Design Bridge (delta)

## MODIFIED Requirements

### Requirement: Design bridge rule for agents

The design-bridge rule deployed to consumer projects SHALL instruct agents on the v0-only design pipeline. When `design-source/` exists in the change directory, that directory IS the design — agents copy the v0 TSX files as starting point, then adapt the integration layer (data, copy, types, backend wiring). Agents MAY refactor code structure (extract components, rename, retype) but MUST NOT change visual contract (className values, JSX structure, shadcn primitive choice, spacing, animations).

#### Scenario: Agent with design-source in change directory
- **WHEN** an agent session starts for a change that has `openspec/changes/<change>/design-source/` populated
- **AND** `.claude/rules/design-bridge.md` is present
- **THEN** the rule instructs: "The files in design-source/ ARE the design. Copy them as the starting point of your implementation."
- **AND** "You MAY refactor code structure: extract repeated JSX into reusable components, rename files to project convention, add TypeScript types, replace mock data with real API/Prisma queries, replace English placeholder copy with HU content from the i18n catalog."
- **AND** "Accessibility additions: aria-* attributes on existing elements (aria-label, role, aria-describedby, aria-hidden) are SAFE and explicitly encouraged. However, adding new DOM elements purely for accessibility (e.g. `<span class='sr-only'>...</span>`) IS a DOM structure change and the fidelity gate will flag it; if you need a visually-hidden element, document it in the change's tasks and accept that the gate will need a per-route threshold override."
- **AND** "You MUST NOT change: Tailwind className values, DOM structure (added/removed wrappers, sibling reorder), shadcn primitive choices (Button stays Button), shadcn variant props, spacing tokens, responsive breakpoints, animation sequences, icon library, globals.css."
- **AND** "Suspense boundaries and Server vs Client component conversions ARE allowed when motivated by data-fetching strategy — but verify the rendered output is unchanged. If a Suspense fallback briefly displays, ensure the gate uses `waitForLoadState('networkidle')` (it does by default)."
- **AND** "The contract is verified by the design-fidelity gate via screenshot diff. Refactor freely in code; if rendered pixels diverge, you've crossed the line."

#### Scenario: Agent without design-source (no v0 export in project)
- **WHEN** an agent session starts in a project where `detect_design_source() == "none"` and no `design-source/` exists in the change
- **THEN** the rule has no effect — agent uses standard shadcn/ui conventions and any project-level design tokens in globals.css

#### Scenario: Refactor policy ambiguity
- **WHEN** the agent is uncertain whether a change crosses the visual contract
- **THEN** the rule directs the agent to: "(a) preserve the v0 output exactly, (b) commit and let the design-fidelity gate decide. If the gate passes, the refactor is safe."

#### Scenario: Agent encounters bugs in v0 source code
- **WHEN** the agent reads v0 design-source files and finds a clear bug (broken import, TypeScript error, missing dependency, hydration mismatch, runtime error)
- **THEN** the rule instructs: "Fix the bug in your worktree implementation, preserving the visual contract (className, JSX structure, shadcn primitives unchanged). Document the fix in the change's commit message with prefix `v0-fix:`. Do NOT propagate the bug to production by claiming 'v0 generated it this way'."
- **AND** "Common fixable v0 bugs: missing import, wrong import path, missing TypeScript types, unused imports, missing 'use client' directive on hooks-using components, missing alt attributes, key prop missing in lists."
- **AND** "If the bug requires a structural change that would fail the fidelity gate (e.g. v0's JSX nesting causes a hydration error and only restructuring fixes it), document the necessary structural change in the change's tasks AND propose a per-route fidelity_threshold override OR file a manifest issue for the scaffold author to regenerate the v0 page."

#### Scenario: Agent encounters inconsistencies between v0 pages
- **WHEN** the agent finds inconsistent patterns across v0 pages (e.g. one page uses shadcn `<Button>`, another uses `<button>` for the same purpose; or component naming varies for the same concept)
- **THEN** the rule instructs: "Standardize on the dominant pattern (whichever appears in more places) and update the inconsistent occurrence to match. Document the standardization in the commit message. The fidelity gate's screenshot diff should still pass because functional/visual output is equivalent."
- **AND** "If standardization would fail the fidelity gate (visual difference), preserve v0's original choice and note the inconsistency in change tasks for the scaffold author to address upstream in v0."

### Requirement: Design context source priority

The design context source priority SHALL be: v0 design-source slice (when v0-export present) > globals.css tokens (always available) > nothing. Markdown design briefs SHALL NOT be used as authoritative design source.

#### Scenario: v0 design-source present
- **WHEN** building dispatch context AND `detect_design_source() == "v0"`
- **THEN** the dispatcher SHALL include the design-source slice + token quick-reference from globals.css
- **AND** SHALL NOT inject any markdown brief content as authoritative design source

#### Scenario: v0 not present, globals.css available
- **WHEN** `detect_design_source() == "none"` AND `shadcn/globals.css` exists
- **THEN** the dispatcher SHALL include only the token quick-reference
- **AND** SHALL NOT block dispatch on missing design source (graceful degradation)

#### Scenario: No design source AND no globals.css
- **WHEN** `detect_design_source() == "none"` AND no `globals.css` is found at any expected path
- **THEN** the dispatcher SHALL still proceed (dispatch is never blocked by missing design content)
- **AND** the agent's input.md SHALL include a `## Design Source` section with the single line: "No design source available — apply project conventions and shadcn/ui defaults."
- **AND** the design-bridge.md rule defaults to: "Without a design source, use the project's shadcn/ui defaults; do not invent custom component variants."

#### Scenario: Optional vibe note
- **WHEN** a `docs/design-brief.md` (or equivalent) exists and is marked non-authoritative
- **THEN** the dispatcher MAY include it as a CONTEXT-ONLY section
- **AND** the section SHALL be labeled `## Design Vibe Notes (non-authoritative)` so the agent does not interpret it as binding requirements
