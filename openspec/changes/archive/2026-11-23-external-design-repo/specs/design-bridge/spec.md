## MODIFIED Requirements

### Requirement: Design bridge rule for agents

The design-bridge rule deployed to consumer projects SHALL use imperative language (MUST/SHALL) instead of passive suggestions. The rule SHALL instruct agents to read `design-snapshot.md` before implementing UI components and use exact token values.

#### Scenario: Agent with design snapshot in project
- **WHEN** an agent session starts in a project that has `design-snapshot.md` in its root
- **AND** `.claude/rules/design-bridge.md` (or `set-design-bridge.md`) is present
- **THEN** the rule instructs: "You MUST read design-snapshot.md BEFORE implementing any UI component"
- **AND** "Use the EXACT color, spacing, typography, and radius values from the Design Tokens section"
- **AND** "Match the component hierarchy structure from the relevant frame in the Component Hierarchy section"

#### Scenario: Agent with external design source
- **WHEN** an agent session starts in a worktree that has `v0-export` symlinked to an external design directory
- **AND** the external directory contains `.set-designer/design-rules/` files
- **THEN** the agent SHALL follow both the design-bridge rule and the injected design rules
- **AND** design tokens SHALL come from the auto-extracted `design-system.md` or the external `app/globals.css`

#### Scenario: Agent with design MCP but no snapshot
- **WHEN** an agent session starts in a project with a registered design MCP
- **AND** no `design-snapshot.md` exists
- **THEN** the rule instructs: "A design MCP is available — you MUST query it for design tokens, component specs, and layout details BEFORE implementing UI elements"

#### Scenario: Agent without design tools
- **WHEN** an agent session starts in a project with no design MCP registered
- **AND** no `design-snapshot.md` exists
- **AND** no external design source configured
- **THEN** the rule has no effect (ignore entirely)

### Requirement: Component-mounting rule
The `design-bridge.md` rule SHALL include an explicit component-mounting directive: when a shell component for a feature exists in the design source's `components/` directory, the agent MUST mount it. The agent MUST NOT create a parallel implementation under a different name.

#### Scenario: Component exists in external design source
- **WHEN** the design source (external or in-project) has a component matching the agent's scope
- **THEN** the agent MUST use that component as the base implementation
