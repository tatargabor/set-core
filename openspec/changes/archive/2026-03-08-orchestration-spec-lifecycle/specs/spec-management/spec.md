## Capability: spec-management

`set-orchestrate specs` subcommand for listing, showing, and archiving spec documents.

## Requirements

### Requirement: List specs

`set-orchestrate specs` (no subcommand) lists all spec files in `wt/orchestration/specs/`:
- Active specs (top-level files) shown first
- Archived specs (in `archive/`) shown under an "Archive:" section
- Each entry shows filename
- If `wt/orchestration/specs/` doesn't exist, print a helpful message

### Requirement: Show spec content

`set-orchestrate specs show <name>` displays the content of a spec file. Uses the same short-name resolution as `--spec`: tries `wt/orchestration/specs/<name>.md` first. Outputs to stdout for piping.

### Requirement: Archive a spec

`set-orchestrate specs archive <name>` moves a spec from `wt/orchestration/specs/<name>.md` to `wt/orchestration/specs/archive/<name>.md`. Uses `git mv` when in a git repo. Errors if the file doesn't exist or is already archived.

### Requirement: Migrate legacy specs

`set-project migrate` detects `docs/v[0-9]*.md` files (legacy spec documents) and offers to move them to `wt/orchestration/specs/archive/`. These are completed specs from past orchestration runs. The migration uses `git mv` when in a git repo.

### Requirement: Graceful degradation

All `specs` subcommands gracefully handle the absence of `wt/orchestration/specs/` — print a message suggesting `set-project init` instead of crashing.
