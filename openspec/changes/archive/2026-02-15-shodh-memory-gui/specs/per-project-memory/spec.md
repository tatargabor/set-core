## ADDED Requirements

### Requirement: Auto-detect project name from git root
The `set-memory` CLI SHALL determine the project name from the basename of `git rev-parse --show-toplevel`. If not inside a git repository, it SHALL fall back to the global storage directory.

#### Scenario: Inside a git repository
- **WHEN** `set-memory` is run from within a git worktree or repo at `/home/user/code/set-core`
- **THEN** storage path is `~/.local/share/set-core/memory/set-core/`

#### Scenario: Outside any git repository
- **WHEN** `set-memory` is run from a non-git directory
- **THEN** storage path is `~/.local/share/set-core/memory/_global/`

#### Scenario: Explicit project override
- **WHEN** `set-memory` is run with `--project my-project`
- **THEN** storage path is `~/.local/share/set-core/memory/my-project/` regardless of git context

### Requirement: Per-project storage isolation
Each project SHALL have its own shodh-memory storage directory. Memories stored for project A SHALL NOT appear in recall results for project B.

#### Scenario: Cross-project isolation
- **WHEN** a memory is saved for project "set-core" and recall is run for project "other-app"
- **THEN** the memory does NOT appear in "other-app" recall results

### Requirement: List projects command
The `set-memory projects` command SHALL list all project directories under the memory storage root, showing project name and memory count.

#### Scenario: Multiple projects with memories
- **WHEN** `set-memory projects` is run and 3 projects have memories
- **THEN** output lists each project name with its memory count

### Requirement: Backward compatibility with existing global storage
If memories exist in the legacy global storage path (`~/.local/share/set-core/memory/` without project subdirectories), the CLI SHALL treat them as belonging to a `_legacy` project. A migration is NOT required — the legacy data stays accessible.

#### Scenario: Legacy storage coexistence
- **WHEN** old-format memories exist in the global storage root and new per-project directories also exist
- **THEN** both are accessible — legacy via `--project _legacy`, new via auto-detect
