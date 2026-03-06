# Orchestration Context Pruning

Reduces token overhead in agent worktrees by removing orchestrator-specific files that Ralph never needs, while preserving files essential for implementation quality.

## Requirements

### R1: Prune Orchestrator Commands
- Remove from worktrees: `.claude/commands/wt/orchestrate*.md`, `.claude/commands/wt/sentinel*.md`, `.claude/commands/wt/manual*.md`
- These are orchestrator/sentinel commands that Ralph agents never invoke
- Executed during `bootstrap_worktree()` after worktree setup

### R2: Preserve Agent-Essential Files
- MUST NOT prune: `.claude/rules/` (path-scoped conventions), `.claude/skills/` (OpenSpec workflow), `.claude/commands/wt/loop*.md` (Ralph loop), `CLAUDE.md` (project instructions)
- These files are essential for agent implementation quality

### R3: Configurable
- `context_pruning` directive in `orchestration.yaml` (default: true)
- When false, no files are pruned (backwards compatible)

### R4: Logging
- Log count of pruned files per worktree: "Pruned N orchestrator-only files from worktree"
- No error if files don't exist (glob may match nothing)

### R5: Integration Point
- Called from `bootstrap_worktree()` in the dispatcher module
- Runs after worktree creation and before Ralph loop dispatch
