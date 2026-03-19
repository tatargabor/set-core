## MODIFIED Requirements

### Requirement: Mandatory README Sections
The guide SHALL define the following mandatory sections in order:
1. Project title and one-line tagline
2. Overview (3-5 sentences + screenshot)
3. Platform & Editor Support table
4. Quick Start (install → first worktree)
5. Features overview (GUI, CLI, Ralph Loop, Team Sync, Developer Memory, MCP)
6. Installation (detailed)
7. CLI Reference (all user-facing commands)
8. Configuration
9. Known Issues & Limitations
10. Claude Code Integration
11. Contributing (link to CONTRIBUTING.md)
12. Use Cases
13. Related Projects
14. Future Development
15. License

#### Scenario: README follows section order
- **WHEN** the README is generated or updated following the guide
- **THEN** all mandatory sections are present in the specified order

## ADDED Requirements

### Requirement: Developer Memory Feature Instructions
The guide's Features section (Section 6) SHALL include detailed generation instructions for the Developer Memory subsection, specifying: one-paragraph overview, three concrete examples (negative experience recall, OpenSpec automatic hooks, mid-flow learning), CLI quick-start commands, link to `docs/developer-memory.md`, and experimental status note.

#### Scenario: Feature section generation
- **WHEN** an LLM generates the Features section using the guide
- **THEN** the Developer Memory subsection includes an overview paragraph, concrete examples, and a link to the deep-dive doc

### Requirement: Developer Memory Use Case Instructions
The guide's Use Cases section (Section 13) SHALL include instructions for a "Developer Memory" use case covering: scenario showing memory saving and recall across sessions, OpenSpec integration scenario (automatic recall at change start), and a "When to use what" table entry for memory.

#### Scenario: Use case generation
- **WHEN** an LLM generates the Use Cases section using the guide
- **THEN** a Developer Memory use case appears with cross-session recall scenario and OpenSpec integration scenario

### Requirement: Developer Memory CLI Reference Instructions
The guide's CLI Reference section (Section 8) SHALL list the Developer Memory category with all `set-memory` and `set-memory-hooks` user-facing commands, requiring a one-line description for each.

#### Scenario: CLI reference completeness
- **WHEN** an LLM generates the CLI Reference following the guide
- **THEN** the Developer Memory category includes `set-memory remember`, `set-memory recall`, `set-memory list`, `set-memory status`, `set-memory-hooks install`, and `set-memory-hooks check`
