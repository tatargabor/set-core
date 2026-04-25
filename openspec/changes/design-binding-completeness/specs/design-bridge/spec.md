## ADDED Requirements

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
