## MODIFIED Requirements

### Requirement: Developer Memory CLI documentation in README
The README CLI Reference SHALL document all user-facing `set-memory` subcommands including sync, proactive, stats, and cleanup.

#### Scenario: All set-memory subcommands listed
- **WHEN** a user reads the Developer Memory CLI table in README
- **THEN** they SHALL see entries for: remember, recall, list, status, forget, context, brain, get, export, import, repair, sync, sync push, sync pull, sync status, proactive, stats, cleanup

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
