## MODIFIED Requirements

### Requirement: set-memory-hooks install command
The `set-memory-hooks install` command SHALL patch memory recall/remember steps into all OpenSpec SKILL.md files in the project's `.claude/skills/openspec-*/SKILL.md` AND all corresponding command files in `.claude/commands/opsx/*.md`. The target list SHALL include 9 skills: openspec-new-change, openspec-continue-change, openspec-ff-change, openspec-apply-change, openspec-archive-change, openspec-explore, openspec-sync-specs, openspec-verify-change, and openspec-bulk-archive-change. The patching SHALL be idempotent — running install twice SHALL produce the same result as running it once.

#### Scenario: Install hooks into fresh OpenSpec skills
- **WHEN** user runs `set-memory-hooks install` in a repo with OpenSpec initialized but no memory hooks
- **THEN** the command patches all 9 target SKILL.md files and corresponding command files with recall/remember steps and exits 0

#### Scenario: Install hooks idempotently
- **WHEN** user runs `set-memory-hooks install` in a repo where hooks are already installed
- **THEN** the command detects existing hooks (via marker comment), skips patching, reports "already installed", and exits 0

#### Scenario: Install when OpenSpec not initialized
- **WHEN** user runs `set-memory-hooks install` in a repo without `.claude/skills/openspec-*/SKILL.md` files
- **THEN** the command exits with error "No OpenSpec skills found" and exit code 1

### Requirement: set-memory-hooks check command
The `set-memory-hooks check` command SHALL check whether memory hooks are installed in all 9 target SKILL.md files. It SHALL output JSON: `{"installed": true/false, "files_total": N, "files_patched": N}`. The check SHALL use the marker comment to detect hooks.

#### Scenario: Check when all hooks installed
- **WHEN** user runs `set-memory-hooks check --json` and all 9 SKILL.md files have hooks
- **THEN** output is `{"installed": true, "files_total": 9, "files_patched": 9}`

#### Scenario: Check when no hooks installed
- **WHEN** user runs `set-memory-hooks check --json` and no SKILL.md files have hooks
- **THEN** output is `{"installed": false, "files_total": 9, "files_patched": 0}`

#### Scenario: Check when OpenSpec not present
- **WHEN** user runs `set-memory-hooks check --json` and no OpenSpec skills exist
- **THEN** output is `{"installed": false, "files_total": 0, "files_patched": 0}`

### Requirement: Hook content and placement
Each target SKILL.md SHALL be patched with specific memory hooks. The hooks SHALL be enclosed in marker comments (`<!-- set-memory hooks start -->` / `<!-- set-memory hooks end -->`) for detection and clean removal.

#### Scenario: Recall hooks in openspec-new-change
- **WHEN** hooks are installed in `openspec-new-change/SKILL.md`
- **THEN** step 1b is added after step 1, containing explicit `set-memory health` check and `set-memory recall "<user-description>" --limit 3 --mode hybrid`

#### Scenario: Memory hooks in openspec-bulk-archive-change
- **WHEN** hooks are installed in `openspec-bulk-archive-change/SKILL.md`
- **THEN** a completion memory step is added containing `set-memory health` check and `set-memory remember` for archival context, decisions, and lessons
