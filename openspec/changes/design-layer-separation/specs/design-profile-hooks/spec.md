# Design Profile Hooks

## ADDED Requirements

## IN SCOPE
- New `ProjectType` ABC methods for design integration (dispatch, review, data model)
- `WebProjectType` implementations that call bridge.sh (moving existing logic)
- Removing bridge.sh subprocess calls from core orchestration modules
- Removing hardcoded Next.js references from compare.py

## OUT OF SCOPE
- Moving `lib/design/` files to `modules/web/` (they're CLI tools, stay in place)
- Changing the design-system.md or design-brief.md format
- Modifying bridge.sh functions themselves
- Adding new design capabilities (shadcn connector, etc.)
- Changing fetcher.py or design_parser.py

### Requirement: Profile-driven design dispatch
The dispatcher SHALL delegate per-change design.md generation to the profile system instead of calling bridge.sh directly.

#### Scenario: Web project with design-brief.md
- **WHEN** dispatcher builds per-change design context for a web project that has design-brief.md
- **THEN** `profile.build_per_change_design(change_name, scope, wt_path)` is called
- **AND** the web module implementation calls bridge.sh `design_brief_for_dispatch()` and `design_context_for_dispatch()`
- **AND** the resulting design.md is identical to current output

#### Scenario: Non-web project with no design
- **WHEN** dispatcher builds per-change design context for a non-web project (e.g., DungeonProjectType)
- **THEN** `profile.build_per_change_design()` returns False (base no-op)
- **AND** no design.md is written
- **AND** no bridge.sh is invoked

#### Scenario: Dispatch enrichment via profile
- **WHEN** dispatcher enriches dispatch context with design tokens and sources
- **THEN** `profile.get_design_dispatch_context(scope, snapshot_dir)` is called
- **AND** the web module implementation calls bridge.sh `design_context_for_dispatch()` and `design_sources_for_dispatch()`
- **AND** the returned string is injected into the dispatch prompt identically to current behavior

### Requirement: Profile-driven design review
The verifier SHALL delegate design compliance review to the profile system instead of calling bridge.sh directly.

#### Scenario: Web project code review
- **WHEN** verifier generates a code review for a web project change
- **THEN** `profile.build_design_review_section(snapshot_dir)` is called
- **AND** the web module implementation calls bridge.sh `build_design_review_section()`
- **AND** the returned compliance text is injected into the review prompt identically

#### Scenario: Non-web project code review
- **WHEN** verifier generates a code review for a non-web project
- **THEN** `profile.build_design_review_section()` returns empty string (base no-op)
- **AND** no design compliance section appears in review

### Requirement: Profile-driven design data model
The planner SHALL delegate design data model extraction to the profile system instead of calling bridge.sh directly.

#### Scenario: Web project with Figma sources
- **WHEN** planner has design context and needs data model extraction
- **THEN** `profile.fetch_design_data_model(project_path)` is called
- **AND** the web module implementation calls bridge.sh `design_data_model_section()`
- **AND** the returned data model text is appended to design context identically

#### Scenario: Non-web project
- **WHEN** planner requests data model for a non-web project
- **THEN** `profile.fetch_design_data_model()` returns empty string (base no-op)

### Requirement: Remove hardcoded web references from compare
The compare tool SHALL use profile methods for template file lists instead of hardcoded Next.js paths.

#### Scenario: Compare uses profile template files
- **WHEN** compare tool checks template compliance
- **THEN** it calls `profile.get_comparison_template_files()` (already exists)
- **AND** hardcoded references to "src/app/globals.css", "next.config.js", "postcss.config.mjs" are removed from core
