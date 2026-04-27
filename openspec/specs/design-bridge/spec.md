# design-bridge Specification

## Purpose

Make the design source first-class in agent dispatch: deploy a project rule that agents must follow before implementing UI, telling them where to read tokens, components, and visual specs from, and which exact values to use.
## Requirements
### Requirement: Design bridge rule for agents

The design-bridge rule deployed to consumer projects SHALL use imperative language (MUST/SHALL) instead of passive suggestions. The rule SHALL instruct agents to read `design-snapshot.md` before implementing UI components and use exact token values.

#### Scenario: Agent with design snapshot in project
- **WHEN** an agent session starts in a project that has `design-snapshot.md` in its root
- **AND** `.claude/rules/design-bridge.md` (or `set-design-bridge.md`) is present
- **THEN** the rule instructs: "You MUST read design-snapshot.md BEFORE implementing any UI component"
- **AND** "Use the EXACT color, spacing, typography, and radius values from the Design Tokens section"
- **AND** "Match the component hierarchy structure from the relevant frame in the Component Hierarchy section"

#### Scenario: Agent with design MCP but no snapshot
- **WHEN** an agent session starts in a project with a registered design MCP
- **AND** no `design-snapshot.md` exists
- **THEN** the rule instructs: "A design MCP is available — you MUST query it for design tokens, component specs, and layout details BEFORE implementing UI elements"

#### Scenario: Agent without design tools
- **WHEN** an agent session starts in a project with no design MCP registered
- **AND** no `design-snapshot.md` exists
- **THEN** the rule has no effect (ignore entirely)

### Requirement: Component-mounting rule
The `design-bridge.md` rule SHALL include an explicit component-mounting directive: when a shell component for a feature exists in the design source's `components/` directory, the agent MUST mount it. The agent MUST NOT create a parallel implementation under a different name.

The rule SHALL include at least one concrete bad/good example pair.

#### Scenario: Bad pattern named in rule
- **WHEN** an agent reads `design-bridge.md`
- **THEN** the rule contains the example: "Bad: agent creates `src/components/search-bar.tsx` while v0 has `search-palette.tsx`"
- **AND** the rule explains: "agent must mount `search-palette.tsx` (rename allowed only via `manifest.shared_aliases`)"

#### Scenario: Good pattern named in rule
- **WHEN** an agent reads `design-bridge.md`
- **THEN** the rule contains the example: "Good: agent imports `SearchPalette` from `@/components/search-palette` (mounted from v0 source) and adapts data via `useQuery` hook"

### Requirement: Entity-reference recognition
The `design-bridge.md` rule SHALL note that spec.md and feature specs use `@component:NAME` and `@route:/PATH` markers to bind to design entities. The agent SHALL treat these markers as MANDATORY references to existing design source files; deviating from a marker is a violation reportable to the operator.

#### Scenario: Agent encounters @component marker in spec
- **GIVEN** a feature spec contains `@component:search-palette`
- **WHEN** the agent implements the feature
- **THEN** the agent imports `SearchPalette` from the design-source-derived path
- **AND** does NOT create a `search-bar.tsx` or similar parallel

