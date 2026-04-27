# Spec: Design Dispatch Context (delta)

## MODIFIED Requirements

### Requirement: Design context extraction for dispatch

The dispatcher SHALL build per-change design context by delegating to the loaded profile's design-source provider. The profile decides what content to include; the dispatcher only orchestrates the call and writes the result to the agent's input. Figma-specific extraction (snapshot fetching, alias matching against design-brief.md, figma-raw source scoring) is REMOVED from the bridge layer.

#### Scenario: Web profile with v0 source
- **GIVEN** the loaded profile is `WebProjectType` AND `detect_design_source() == "v0"`
- **WHEN** the dispatcher builds context for a change
- **THEN** the profile's `get_design_dispatch_context(scope, project_path)` is called
- **AND** the profile returns a markdown block referring to `openspec/changes/<change>/design-source/`
- **AND** the dispatcher writes that block into `input.md`

#### Scenario: Profile with no design source
- **GIVEN** `detect_design_source() == "none"`
- **WHEN** the dispatcher builds context
- **THEN** the profile returns an empty string OR a token-only quick-reference (when `globals.css` exists)
- **AND** dispatch is NOT blocked by absent design context

#### Scenario: Bridge layer Figma extraction removed
- **WHEN** the bridge layer is invoked
- **THEN** it SHALL NOT attempt to read `design-snapshot.md`, `design-system.md`, `figma-raw/*/sources/`, or `design-brief.md` as authoritative design source
- **AND** legacy alias matching against design-brief.md sections SHALL NOT execute
- **AND** any environment variables for Figma URL / snapshot path SHALL be ignored (logged at DEBUG)
