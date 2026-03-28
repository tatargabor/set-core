# Spec: docs-site-structure

## ADDED Requirements

## IN SCOPE
- README.md rewrite (~200 lines, orchestration-first)
- docs/ restructure into guide/, reference/, learn/ hierarchy
- INDEX.md navigation map with reading paths by user type
- Archive old prose docs to docs/archive/
- Embed auto-generated screenshots from docs/images/auto/
- Spec-doc cross-references for future updateability
- Example workflow walkthroughs (minishop, micro-web)

## OUT OF SCOPE
- Rewriting howitworks/ chapters (keep as-is, reference from learn/)
- Translating new docs to Hungarian
- Building a docs website (static site generator)
- Changing any code or functionality

### Requirement: README orchestration-first narrative

The README SHALL present set-core as an autonomous orchestration system, leading with the problem it solves and the orchestration workflow as the primary use case.

#### Scenario: First-time visitor understands purpose in 30 seconds
- **WHEN** a developer opens the GitHub README
- **THEN** they understand within the first 3 paragraphs: what set-core does (autonomous multi-agent orchestration), how it works (spec → plan → parallel agents → quality gates → merge), and what the result looks like (screenshot of dashboard + built app)

#### Scenario: README under 200 lines
- **WHEN** the README is rendered on GitHub
- **THEN** it contains no more than 200 lines, with detailed content linked to docs/

### Requirement: Documentation hierarchy

The docs/ directory SHALL be organized into three tiers: guide (how-to workflows), reference (lookup), and learn (deep dives).

#### Scenario: Guide section covers common workflows
- **WHEN** a user wants to run their first orchestration
- **THEN** docs/guide/quick-start.md walks them through the complete flow with screenshots

#### Scenario: Reference section is complete
- **WHEN** a user needs to look up a CLI command, config option, or API
- **THEN** docs/reference/ has a dedicated page with all options documented

#### Scenario: Learn section links to deep content
- **WHEN** a user wants to understand how the orchestration engine works internally
- **THEN** docs/learn/ links to the howitworks/ chapters and benchmark reports

### Requirement: Navigation index

A docs/INDEX.md SHALL provide a site map with reading paths for different user types.

#### Scenario: Navigation by user type
- **WHEN** a solo developer, team lead, or contributor visits INDEX.md
- **THEN** they find a recommended reading path for their role

### Requirement: Archive old docs

Old prose documentation SHALL be moved to docs/archive/ without deletion, preserving git history.

#### Scenario: Old docs accessible but not prominent
- **WHEN** someone looks for old documentation
- **THEN** they find it in docs/archive/ with original filenames

#### Scenario: Only prose docs archived
- **WHEN** archiving docs
- **THEN** skill files, design rules, CLAUDE.md, and config references are NOT moved

### Requirement: Screenshot integration

Documentation pages SHALL embed auto-generated screenshots from the screenshot pipeline.

#### Scenario: Dashboard screenshots in guide
- **WHEN** the orchestration guide describes the dashboard
- **THEN** it includes screenshots from docs/images/auto/web/

#### Scenario: CLI screenshots in reference
- **WHEN** the CLI reference describes a command
- **THEN** it includes the terminal screenshot from docs/images/auto/cli/

#### Scenario: App screenshots in examples
- **WHEN** an example walkthrough shows the built application
- **THEN** it includes screenshots from docs/images/auto/app/

### Requirement: Spec-doc cross-references

Each major documentation section SHALL reference the openspec/specs/ capability it documents, enabling future updates.

#### Scenario: Doc section links to spec
- **WHEN** a documentation section describes a feature (e.g., quality gates)
- **THEN** it includes a footer comment like `<!-- spec: verify-gate, merge-retry, gate-profiles -->`

#### Scenario: Spec change triggers doc update awareness
- **WHEN** a developer modifies or adds an openspec spec
- **THEN** they can grep for the spec name in docs/ to find which documentation sections need updating
