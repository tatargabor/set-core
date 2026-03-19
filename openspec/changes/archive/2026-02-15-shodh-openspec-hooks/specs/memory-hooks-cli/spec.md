## ADDED Requirements

### Requirement: set-memory-hooks install command
The `set-memory-hooks install` command SHALL patch memory recall/remember steps into all OpenSpec SKILL.md files in the project's `.claude/skills/openspec-*/SKILL.md`. The patching SHALL be idempotent — running install twice SHALL produce the same result as running it once. The command SHALL accept a `--project` flag or auto-detect the project from `git rev-parse --show-toplevel`.

#### Scenario: Install hooks into fresh OpenSpec skills
- **WHEN** user runs `set-memory-hooks install` in a repo with OpenSpec initialized but no memory hooks
- **THEN** the command patches all 5 target SKILL.md files with recall/remember steps and exits 0

#### Scenario: Install hooks idempotently
- **WHEN** user runs `set-memory-hooks install` in a repo where hooks are already installed
- **THEN** the command detects existing hooks (via marker comment), skips patching, reports "already installed", and exits 0

#### Scenario: Install when OpenSpec not initialized
- **WHEN** user runs `set-memory-hooks install` in a repo without `.claude/skills/openspec-*/SKILL.md` files
- **THEN** the command exits with error "No OpenSpec skills found" and exit code 1

### Requirement: Hook content and placement
Each target SKILL.md SHALL be patched with specific memory hooks. The hooks SHALL be enclosed in marker comments (`# --- set-memory hooks start ---` / `# --- set-memory hooks end ---`) for detection and clean removal. The hook content SHALL match the patterns defined in the shodh-memory-integration change.

#### Scenario: Recall hooks in openspec-new-change
- **WHEN** hooks are installed in `openspec-new-change/SKILL.md`
- **THEN** step 1b is added after step 1, containing `set-memory health` check and `set-memory recall "<user-description>" --limit 3`

#### Scenario: Recall hooks in openspec-continue-change
- **WHEN** hooks are installed in `openspec-continue-change/SKILL.md`
- **THEN** step 2b is added after step 2, containing `set-memory health` check and `set-memory recall "<change-name> <keywords>" --limit 5`

#### Scenario: Recall hooks in openspec-ff-change
- **WHEN** hooks are installed in `openspec-ff-change/SKILL.md`
- **THEN** step 3b is added after step 3, containing `set-memory health` check and `set-memory recall "<change-name> <description>" --limit 5`

#### Scenario: Recall and remember hooks in openspec-apply-change
- **WHEN** hooks are installed in `openspec-apply-change/SKILL.md`
- **THEN** step 4b is added with recall, and step 7 is extended with remember (save errors as Observation, patterns as Learning, completion as Event)

#### Scenario: Remember hooks in openspec-archive-change
- **WHEN** hooks are installed in `openspec-archive-change/SKILL.md`
- **THEN** step 7 is added with remember (save decisions as Decision, lessons as Learning, completion as Event)

### Requirement: set-memory-hooks check command
The `set-memory-hooks check` command SHALL check whether memory hooks are installed in all target SKILL.md files. It SHALL output JSON: `{"installed": true/false, "files_total": N, "files_patched": N}`. The check SHALL use the marker comment to detect hooks, completing in under 5ms.

#### Scenario: Check when all hooks installed
- **WHEN** user runs `set-memory-hooks check --json` and all 5 SKILL.md files have hooks
- **THEN** output is `{"installed": true, "files_total": 5, "files_patched": 5}`

#### Scenario: Check when no hooks installed
- **WHEN** user runs `set-memory-hooks check --json` and no SKILL.md files have hooks
- **THEN** output is `{"installed": false, "files_total": 5, "files_patched": 0}`

#### Scenario: Check when OpenSpec not present
- **WHEN** user runs `set-memory-hooks check --json` and no OpenSpec skills exist
- **THEN** output is `{"installed": false, "files_total": 0, "files_patched": 0}`

### Requirement: set-memory-hooks remove command
The `set-memory-hooks remove` command SHALL remove all memory hooks from OpenSpec SKILL.md files by deleting content between marker comments (inclusive). The removal SHALL be idempotent.

#### Scenario: Remove installed hooks
- **WHEN** user runs `set-memory-hooks remove` and hooks are installed
- **THEN** all hook content between markers is removed, SKILL.md files return to their pre-hook state, exit code 0

#### Scenario: Remove when no hooks present
- **WHEN** user runs `set-memory-hooks remove` and no hooks are installed
- **THEN** the command reports "no hooks found" and exits 0
