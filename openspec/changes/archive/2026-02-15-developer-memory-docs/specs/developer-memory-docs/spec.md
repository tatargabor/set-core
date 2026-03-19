## ADDED Requirements

### Requirement: Developer Memory User Guide
The project SHALL have a `docs/developer-memory.md` file that serves as the comprehensive user-facing guide for the developer memory system.

#### Scenario: Guide file exists
- **WHEN** a user looks for memory documentation
- **THEN** `docs/developer-memory.md` exists with complete usage instructions

### Requirement: Quick Start Section
The guide SHALL begin with a Quick Start showing the three essential commands: health check, remember, and recall.

#### Scenario: User follows quick start
- **WHEN** a new user reads the Quick Start section
- **THEN** they see `set-memory health`, a `remember` example with piped content, and a `recall` example with a query

### Requirement: Use Case Examples
The guide SHALL include at least four concrete use case scenarios demonstrating when developer memory is valuable, each with realistic shell commands and expected outputs.

#### Scenario: Negative past experience
- **WHEN** a user reads the "Avoiding repeated mistakes" use case
- **THEN** they see a scenario where an agent saves a failure (Learning type) and a future agent recalls it to avoid the same mistake

#### Scenario: Project decisions
- **WHEN** a user reads the "Project decisions" use case
- **THEN** they see a scenario where a decision is saved (Decision type) and recalled when a related change starts

#### Scenario: Technical gotchas
- **WHEN** a user reads the "Technical gotchas" use case
- **THEN** they see a scenario where a non-obvious behavior is saved (Learning type) during implementation

#### Scenario: Background context
- **WHEN** a user reads the "Background context" use case
- **THEN** they see a scenario where project context is saved (Context type) for onboarding future agents

### Requirement: Memory Types Documentation
The guide SHALL document all three memory types (Decision, Learning, Context) with a comparison table showing when to use each and a concrete example per type.

#### Scenario: Types table
- **WHEN** a user reads the Memory Types section
- **THEN** they see a table with columns: Type, When to use, Example

### Requirement: OpenSpec Integration Documentation
The guide SHALL document how memory integrates with each OpenSpec phase, including an ASCII flow diagram and a detailed phase-by-phase table.

#### Scenario: Phase diagram
- **WHEN** a user reads the OpenSpec Integration section
- **THEN** they see an ASCII diagram showing all 6 skill phases (new, continue, ff, apply, archive, explore) with recall/remember annotations

#### Scenario: Phase detail table
- **WHEN** a user reads the phase table
- **THEN** each row shows: Phase name, Hook type (recall/remember/both), What happens automatically, Example scenario

### Requirement: GUI Documentation
The guide SHALL document the GUI memory features: the [M] button, Browse Memories dialog, Remember Note dialog, and hook installation from the menu.

#### Scenario: GUI features listed
- **WHEN** a user reads the GUI section
- **THEN** they find descriptions of the browse dialog (search + card view), remember dialog (type + content + tags), and menu-based hook installation

### Requirement: Ambient Memory Documentation
The guide SHALL explain how proactive/ambient memory works outside of OpenSpec — when agents save knowledge during regular conversations.

#### Scenario: Ambient behavior explained
- **WHEN** a user reads the Ambient Memory section
- **THEN** they understand that agents recognize and save knowledge (negative experience, decisions, learnings) during any conversation, not just during OpenSpec workflows

### Requirement: CLI Reference Section
The guide SHALL include a complete CLI reference for `set-memory` and `set-memory-hooks` with all subcommands, flags, and examples.

#### Scenario: CLI completeness
- **WHEN** a user reads the CLI Reference
- **THEN** they find entries for: `health`, `remember` (with --type and --tags), `recall` (with --limit), `list`, `status` (with --json), `projects`, and `set-memory-hooks` commands (`install`, `check`, `remove`)

### Requirement: Setup Section
The guide SHALL include setup instructions covering `pip install shodh-memory`, `set-memory-hooks install`, and the graceful degradation behavior.

#### Scenario: Setup steps
- **WHEN** a user reads the Setup section
- **THEN** they find: installation command, hooks installation command, and a note that everything silently no-ops if shodh-memory is not installed

### Requirement: Technical Architecture Appendix
The guide SHALL end with a technical architecture appendix containing an ASCII diagram showing the layer stack: Agent Session → CLI → shodh-memory/RocksDB storage.

#### Scenario: Architecture diagram
- **WHEN** a user reads the Architecture appendix
- **THEN** they see a diagram showing three input paths (CLAUDE.md ambient, OpenSpec hooks, /wt:memory manual) feeding into `set-memory` CLI, which uses `shodh-memory` with per-project RocksDB storage
