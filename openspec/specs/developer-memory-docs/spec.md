# developer-memory-docs Specification

## Purpose
Documents the developer memory system across README, docs/developer-memory.md, and GUI, ensuring all CLI commands, features, and integration points are covered.
## Requirements
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
The guide SHALL document the GUI memory features: the [M] button, Browse Memories dialog, Remember Note dialog, hook installation from the menu, and include a screenshot showing the M/O/R status badges.

#### Scenario: GUI features listed
- **WHEN** a user reads the GUI section
- **THEN** they find descriptions of the browse dialog (search + card view), remember dialog (type + content + tags), and menu-based hook installation

#### Scenario: GUI screenshot present
- **WHEN** a user reads the GUI section
- **THEN** they see a screenshot showing the Control Center with [M], [O], and [R] status badges in the project header rows

### Requirement: Ambient Memory Documentation
The guide SHALL explain how proactive/ambient memory works outside of OpenSpec — when agents save knowledge during regular conversations.

#### Scenario: Ambient behavior explained
- **WHEN** a user reads the Ambient Memory section
- **THEN** they understand that agents recognize and save knowledge (negative experience, decisions, learnings) during any conversation, not just during OpenSpec workflows

### Requirement: CLI Reference Section
The guide SHALL include a complete CLI reference for `set-memory` and `set-memory-hooks` with all subcommands, flags, and examples.

#### Scenario: CLI completeness
- **WHEN** a user reads the CLI Reference
- **THEN** they find entries for: `health`, `remember` (with --type and --tags), `recall` (with --limit, --mode, --tags), `list`, `status` (with --json), `projects`, `forget` (with --all, --older-than, --tags, --pattern), `context`, `brain`, `get`, `export`, `import`, `sync`, `migrate`, `repair`, `audit` (with --threshold, --json), `dedup` (with --threshold, --dry-run, --interactive), and `set-memory-hooks` commands (`install`, `check`, `remove`)

#### Scenario: Audit command documented
- **WHEN** a user reads the CLI Reference Diagnostics section
- **THEN** they find `set-memory audit [--threshold N] [--json]` with description: "Report memory health: duplicate clusters, redundancy stats, top clusters"

#### Scenario: Dedup command documented
- **WHEN** a user reads the CLI Reference Diagnostics section
- **THEN** they find `set-memory dedup [--threshold N] [--dry-run] [--interactive]` with description: "Remove duplicate memories, keeping best per cluster with merged tags"

### Requirement: Setup Section
The guide SHALL include setup instructions covering `pip install shodh-memory`, `set-memory-hooks install`, graceful degradation behavior, and step-by-step happy-flow guides for common setup scenarios.

#### Scenario: Setup steps
- **WHEN** a user reads the Setup section
- **THEN** they find: installation command, hooks installation command, and a note that everything silently no-ops if shodh-memory is not installed

#### Scenario: Fresh project init flow
- **WHEN** a user reads the Quick Setup Flows subsection
- **THEN** they find a numbered sequence for initializing a fresh project with OpenSpec and memory: pip install shodh-memory, set-project init (deploys hooks+commands+skills), wt-openspec init, set-memory-hooks install, set-memory-hooks check

#### Scenario: Add memory to existing project flow
- **WHEN** a user reads the Quick Setup Flows subsection
- **THEN** they find a numbered sequence for adding memory to an existing OpenSpec project: pip install shodh-memory (if needed), set-project init (re-run to update deployment), set-memory-hooks install, set-memory-hooks check

#### Scenario: Re-install hooks after update flow
- **WHEN** a user reads the Quick Setup Flows subsection
- **THEN** they find a numbered sequence for re-installing memory hooks after `wt-openspec update`: wt-openspec update, set-memory-hooks install, set-memory-hooks check

### Requirement: Technical Architecture Appendix
The guide SHALL end with a technical architecture appendix containing an ASCII diagram showing the layer stack: Agent Session → CLI → shodh-memory/RocksDB storage.

#### Scenario: Architecture diagram
- **WHEN** a user reads the Architecture appendix
- **THEN** they see a diagram showing three input paths (CLAUDE.md ambient, OpenSpec hooks, /wt:memory manual) feeding into `set-memory` CLI, which uses `shodh-memory` with per-project RocksDB storage

### Requirement: Developer Memory CLI documentation in README
The README CLI Reference SHALL document all user-facing `set-memory` subcommands including audit, dedup, sync, proactive, stats, and cleanup.

#### Scenario: All set-memory subcommands listed
- **WHEN** a user reads the Developer Memory CLI table in README
- **THEN** they SHALL see entries for: remember, recall, list, status, forget, context, brain, get, export, import, repair, sync, sync push, sync pull, sync status, proactive, stats, cleanup, audit, dedup

#### Scenario: Audit and dedup in README CLI table
- **WHEN** a user reads the Developer Memory CLI table in README
- **THEN** they SHALL see `set-memory audit` described as diagnostic report and `set-memory dedup` described as duplicate removal

#### Scenario: set-memory-hooks commands listed
- **WHEN** a user reads the Developer Memory CLI table
- **THEN** they SHALL see entries for: set-memory-hooks install, set-memory-hooks check, set-memory-hooks remove

### Requirement: GUI memory features documented in README
The README Features section SHALL describe the GUI memory capabilities.

#### Scenario: GUI memory features visible in README
- **WHEN** a user reads the Developer Memory feature section
- **THEN** they SHALL see mention of: [M] button, Browse Memories dialog (summary/list modes), Remember Note, Export/Import buttons, semantic search

### Requirement: Memory hooks in internal scripts note
The README internal scripts note SHALL list `wt-hook-memory-recall` and `wt-hook-memory-save` alongside the existing `wt-hook-skill` and `wt-hook-stop`.

#### Scenario: All hook scripts listed
- **WHEN** a user expands the internal scripts section
- **THEN** they SHALL see all 4 hook scripts: wt-hook-skill, wt-hook-stop, wt-hook-memory-recall, wt-hook-memory-save

### Requirement: Automatic hooks documentation includes staging
The guide SHALL document the staging+debounce pattern used by `wt-hook-memory-save` for transcript extraction, explaining that it prevents duplicate memories by staging extractions and committing on session switch.

#### Scenario: Staging pattern documented
- **WHEN** a user reads the automatic hooks section for wt-hook-memory-save
- **THEN** they find a description of the staging mechanism: extractions written to `.set-core/.staged-extract-*`, committed when a different transcript is detected, debounced at 5-minute intervals

### Requirement: README guide includes audit and dedup in mandatory list
The `docs/readme-guide.md` mandatory Developer Memory CLI list SHALL include `set-memory audit` and `set-memory dedup`.

#### Scenario: Mandatory list updated
- **WHEN** the README is generated using readme-guide.md
- **THEN** the mandatory CLI list includes `set-memory audit` and `set-memory dedup` alongside existing commands

### Requirement: Comparison with Claude Code built-in memory
The guide SHALL include a section explaining how set-memory differs from Claude Code's built-in memory system (CLAUDE.md files + auto memory), positioned after the Quick Start section.

#### Scenario: Comparison section exists
- **WHEN** a user reads the guide after Quick Start
- **THEN** they find a "How set-memory Differs from Claude Code Memory" section

#### Scenario: Complementary framing
- **WHEN** a user reads the comparison section
- **THEN** they understand that CLAUDE.md/auto memory provides instructions (always loaded, deterministic) while set-memory provides experience (searched on demand, semantic), and they are complementary

#### Scenario: Comparison table
- **WHEN** a user reads the comparison section
- **THEN** they find a table comparing at minimum: storage mechanism, recall method, structure, scale, worktree behavior, team sharing, and lifecycle management

#### Scenario: Worktree sharing difference highlighted
- **WHEN** a user reads the comparison section
- **THEN** they understand that Claude auto memory gives separate memory per worktree while set-memory shares across worktrees of the same repo

### Requirement: set-project init documentation in README
The README Quick Start and CLI Reference SHALL reflect the enhanced `set-project init` behavior that deploys hooks, commands, and skills per-project.

#### Scenario: Quick Start mentions deploy
- **WHEN** a user reads the README Quick Start step for `set-project init`
- **THEN** they understand it registers the project AND deploys set-core hooks, commands, and skills to the project's `.claude/` directory

#### Scenario: CLI Reference updated
- **WHEN** a user reads the Worktree Management CLI table for `set-project`
- **THEN** the description mentions that `init` deploys hooks, commands, and skills (not just registers)

