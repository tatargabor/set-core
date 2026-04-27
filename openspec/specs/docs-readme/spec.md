# Docs Readme Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: README length constraint
README.md SHALL be between 150 and 200 lines. Content exceeding this budget SHALL be moved to dedicated doc pages with links.

#### Scenario: Line count check
- **WHEN** counting lines in the final README.md
- **THEN** the count SHALL be between 150 and 200 lines (excluding blank lines in collapsed sections)

### Requirement: Sentinel-first narrative
The README overview SHALL lead with the sentinel/orchestration value proposition: "give it a spec, get merged features." The Control Center GUI SHALL be mentioned as a monitoring tool, not as the primary feature.

#### Scenario: First paragraph content
- **WHEN** reading the Overview section
- **THEN** the first sentence SHALL reference autonomous orchestration or sentinel, not the GUI
- **AND** the GUI SHALL appear after orchestration in the feature order

### Requirement: README section structure
The README SHALL contain exactly these sections in this order:

1. **Header**: Project name, sentinel-focused tagline, latest update date
2. **Overview**: 5-7 sentences, sentinel-first, modularity note, screenshot
3. **Quick Start**: 5 commands max (clone, init, sentinel run)
4. **Features**: 1-2 sentences per feature, each linking to its doc page. Feature order: Sentinel & Orchestration, Worktrees, Ralph Loop, Developer Memory, Control Center GUI, Team Sync, MCP Server
5. **Plugins**: 3-5 sentences explaining the plugin concept, link to docs/plugins.md
6. **Installation**: Brief prerequisites + install command, link to docs/getting-started.md
7. **Platform Support**: Table (Linux/macOS/Windows/editors)
8. **Related Projects**: Inside a `<details>` collapsed section. Feature comparison matrix retained
9. **Contributing**: 1 line + link to CONTRIBUTING.md
10. **License**: 1 line + link to LICENSE

#### Scenario: Section order verification
- **WHEN** parsing README.md headings
- **THEN** they SHALL appear in the order listed above

#### Scenario: Feature links
- **WHEN** each feature is listed in the Features section
- **THEN** it SHALL include a markdown link to its dedicated doc page

### Requirement: Quick Start sentinel-oriented
The Quick Start SHALL show the sentinel workflow as the primary path, not just worktree creation.

#### Scenario: Quick Start commands
- **WHEN** reading the Quick Start section
- **THEN** it SHALL include steps for: install, project init, and running the sentinel with a spec
- **AND** each step SHALL be one command with a one-line comment

### Requirement: Architecture diagram simplification
The README SHALL contain a simplified sentinel-centric architecture diagram (5-7 lines). The full 4-layer diagram SHALL move to `docs/architecture.md`.

#### Scenario: Diagram in README
- **WHEN** viewing the README architecture diagram
- **THEN** it SHALL show: spec → sentinel → orchestrate → worktrees → merged code
- **AND** it SHALL be no more than 10 lines of ASCII art

### Requirement: Feature order reflects priority
Features in the README SHALL be ordered by importance to the sentinel narrative, not alphabetically or by implementation order.

#### Scenario: Feature ordering
- **WHEN** listing features in the README
- **THEN** the order SHALL be: Sentinel & Orchestration, Worktrees, Ralph Loop, Developer Memory, Control Center GUI, Team Sync & Messaging, MCP Server
