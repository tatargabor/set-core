## MODIFIED Requirements

### Requirement: Design bridge rule for agents

The design-bridge rule deployed to consumer projects SHALL use imperative language (MUST/SHALL) instead of passive suggestions. The rule SHALL instruct agents to read `design-snapshot.md` before implementing UI components and use exact token values.

#### Scenario: Agent with design snapshot in project
- **WHEN** an agent session starts in a project that has `design-snapshot.md` in its root
- **AND** `.claude/rules/design-bridge.md` (or `wt-design-bridge.md`) is present
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
