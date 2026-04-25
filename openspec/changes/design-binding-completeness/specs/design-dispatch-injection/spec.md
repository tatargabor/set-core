## ADDED Requirements

### Requirement: design_components autopopulated into Focus files
The dispatcher SHALL include the change's `design_components` in the `## Focus files for this change` section of the agent's `input.md`. A directive line SHALL precede the listing, instructing the agent to mount these components from the design source rather than reimplementing them.

#### Scenario: Focus files contain design_components paths
- **WHEN** dispatcher writes `input.md` for a change with `design_components: ["v0-export/components/search-palette.tsx", "v0-export/components/site-header.tsx"]`
- **THEN** the input.md `## Focus files for this change` section contains both paths
- **AND** the section is preceded by: "**Mount these components from the design source. DO NOT create parallel implementations under different names.**"

#### Scenario: Empty design_components produces no design Focus mention
- **WHEN** a change has `design_components: []`
- **THEN** the input.md does not include design Focus entries
- **AND** other Focus files (from existing logic) appear normally

#### Scenario: Design_components appended to existing Focus list
- **GIVEN** existing Focus files logic produces a list including `v0-export/lib/utils.ts`
- **WHEN** `design_components` adds `v0-export/components/search-palette.tsx`
- **THEN** the merged Focus files list contains both, deduplicated
