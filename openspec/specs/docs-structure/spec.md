# Docs Structure Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Documentation site map
The project SHALL maintain a documentation structure with README.md as the entry point and dedicated pages in `docs/` for each feature group. The complete page inventory:

| Page | Purpose |
|------|---------|
| `README.md` | Landing page (~150-200 lines) |
| `docs/getting-started.md` | Detailed installation and first-run guide |
| `docs/sentinel.md` | Sentinel supervisor (existing, add nav) |
| `docs/orchestration.md` | Orchestration engine (existing, add nav) |
| `docs/worktrees.md` | Worktree management CLI and use cases |
| `docs/ralph.md` | Ralph loop autonomous execution |
| `docs/developer-memory.md` | Developer memory system (existing, add nav) |
| `docs/gui.md` | Control Center GUI details |
| `docs/team-sync.md` | Team sync, messaging, cross-machine coordination |
| `docs/mcp-server.md` | MCP server setup and tool reference |
| `docs/plugins.md` | Plugin system concept and registry |
| `docs/cli-reference.md` | Complete CLI command reference |
| `docs/configuration.md` | All configuration files and settings |
| `docs/architecture.md` | Technical architecture, diagrams, vision |
| `docs/project-management.md` | Consumer project setup (existing, add nav) |

#### Scenario: All pages exist
- **WHEN** the documentation restructure is complete
- **THEN** every page listed in the site map SHALL exist with content

#### Scenario: No orphan content
- **WHEN** comparing old README content against new documentation
- **THEN** every substantive section from the old README SHALL have a home in one of the new pages

### Requirement: Navigation pattern
Every doc page in `docs/` SHALL include a navigation header at the top linking back to README.md, and a "See also" footer linking to related pages.

#### Scenario: Navigation header format
- **WHEN** viewing any doc page in `docs/`
- **THEN** the first line SHALL be `[< Back to README](../README.md)` (or equivalent relative path)

#### Scenario: Related page links
- **WHEN** viewing any doc page in `docs/`
- **THEN** the page SHALL end with a "See also" section containing links to 2-5 related pages

### Requirement: Content migration completeness
When migrating content from the old README to new doc pages, no substantive content SHALL be lost. A verification step SHALL compare old README sections against new page content.

#### Scenario: CLI reference migration
- **WHEN** the old README CLI Reference section is compared to `docs/cli-reference.md`
- **THEN** every command from the old README SHALL appear in `docs/cli-reference.md`

#### Scenario: Use case distribution
- **WHEN** use cases from the old README are distributed to feature pages
- **THEN** each use case SHALL appear in its corresponding feature page (e.g., "Ralph Loop" use case in `docs/ralph.md`)

### Requirement: agent-messaging.md consolidation
The content of `docs/agent-messaging.md` SHALL be merged into `docs/team-sync.md`. The original file SHALL be replaced with a redirect note pointing to `team-sync.md`.

#### Scenario: Redirect in place
- **WHEN** a user opens `docs/agent-messaging.md`
- **THEN** they SHALL see a note: "This content has moved to [team-sync.md](team-sync.md)"

#### Scenario: No content loss
- **WHEN** comparing old `agent-messaging.md` content with `docs/team-sync.md`
- **THEN** all use cases, architecture notes, and examples SHALL be present in `team-sync.md`

### Requirement: readme-guide.md update
The `docs/readme-guide.md` SHALL be rewritten to match the new README structure (10 sections max). The guide SHALL remain the authoritative source for README generation/regeneration.

#### Scenario: Section count
- **WHEN** the guide defines mandatory README sections
- **THEN** there SHALL be at most 10 mandatory sections

#### Scenario: Regenerability
- **WHEN** an LLM is given the updated `docs/readme-guide.md` and the existing doc pages
- **THEN** it SHALL be able to produce a README.md consistent with the current structure
