## MODIFIED Requirements

### Requirement: Design prompt section generation
The system SHALL generate a prompt section that instructs LLMs to use design MCP tools when available. When a cached design snapshot exists, the prompt section SHALL include the full snapshot content instead of generic instructions.

#### Scenario: Prompt with cached design snapshot
- **WHEN** `design_prompt_section "figma"` is called
- **AND** `$STATE_DIR/design-snapshot.md` exists and is non-empty
- **THEN** the output includes the full snapshot content prefixed with a "Design Context (Snapshot)" header
- **AND** a note that the design MCP is also available for live queries during implementation

#### Scenario: Prompt without snapshot (fallback to generic)
- **WHEN** `design_prompt_section "figma"` is called
- **AND** no cached snapshot exists at `$STATE_DIR/design-snapshot.md`
- **THEN** the output includes generic design tool capabilities and query instructions (existing behavior)

#### Scenario: Prompt with design file reference
- **WHEN** `design_prompt_section "figma"` is called and `DESIGN_FILE_REF` is set
- **AND** no cached snapshot exists
- **THEN** the output includes design tool name, available query types (frames, components, tokens, layout), the file reference, and instructions to flag missing frames as ambiguities
