## ADDED Requirements

### Requirement: Automatic memory save after Write tool
When `handle_post_tool()` receives a Write tool event, it SHALL extract the `file_path` from `tool_input` and save a Learning memory with the format: `Modified <file_path> (new file)`. The save SHALL use `wt-memory remember --type Learning --tags "phase:write-save,source:hook"`.

#### Scenario: New file created
- **WHEN** PostToolUse fires for Write tool with `file_path: "src/components/Button.tsx"`
- **THEN** a Learning memory SHALL be saved: `Modified src/components/Button.tsx (new file)`
- **AND** tags SHALL include `phase:write-save,source:hook`

### Requirement: Automatic memory save after Edit tool
When `handle_post_tool()` receives an Edit tool event, it SHALL extract `file_path` and `old_string` (first 100 chars) from `tool_input` and save a Learning memory with the format: `Modified <file_path>: <old_string_preview> → changed`.

#### Scenario: File edited
- **WHEN** PostToolUse fires for Edit tool with `file_path: "bin/wt-hook-memory"` and `old_string: "if [[ \"$TOOL_NAME\" != \"Read\""`
- **THEN** a Learning memory SHALL be saved: `Modified bin/wt-hook-memory: if [[ "$TOOL_NAME" != "Read" → changed`
- **AND** tags SHALL include `phase:write-save,source:hook`

### Requirement: Automatic memory save after git commit
When `handle_post_tool()` receives a Bash tool event and the command matches `git commit`, it SHALL extract the commit message and save a Learning memory with the format: `Committed: <commit_message>`.

#### Scenario: Git commit via Bash
- **WHEN** PostToolUse fires for Bash tool with command containing `git commit -m "fix: add checkpoint saves"`
- **THEN** a Learning memory SHALL be saved: `Committed: fix: add checkpoint saves`
- **AND** tags SHALL include `phase:write-save,source:hook,git-commit`

#### Scenario: Bash command without git commit
- **WHEN** PostToolUse fires for Bash tool with command `ls -la src/`
- **THEN** no write-save SHALL execute
- **AND** the existing Read/Bash recall logic SHALL proceed normally

### Requirement: Write-save dedup by file path
Write and Edit saves SHALL be deduplicated per file path per session. Only the first modification of a given file SHALL be saved. Subsequent edits to the same file SHALL be skipped. The dedup key format SHALL be `WriteSave:<tool>:<file_path>`.

#### Scenario: First edit to a file
- **WHEN** Edit tool fires for `src/app.ts` for the first time in this session
- **THEN** a write-save memory SHALL be created
- **AND** the dedup key `WriteSave:Edit:src/app.ts` SHALL be stored

#### Scenario: Second edit to same file
- **WHEN** Edit tool fires for `src/app.ts` again in the same session
- **AND** the dedup key `WriteSave:Edit:src/app.ts` already exists
- **THEN** no write-save memory SHALL be created

#### Scenario: Edit and Write to different files
- **WHEN** Edit tool fires for `src/a.ts` and Write tool fires for `src/b.ts`
- **THEN** both SHALL save (different dedup keys)

### Requirement: Write-save does not block recall
After performing a write-save (or skipping due to dedup), the handler SHALL continue with normal PostToolUse recall logic for Read and Bash tools. For Write/Edit tools, the handler SHALL exit after the write-save (no recall injection needed for writes).

#### Scenario: Write tool — save then exit
- **WHEN** PostToolUse fires for Write tool
- **THEN** the write-save SHALL execute
- **AND** the handler SHALL exit without recall injection

#### Scenario: Bash with git commit — save then recall
- **WHEN** PostToolUse fires for Bash tool with `git commit`
- **THEN** the write-save SHALL execute for the commit
- **AND** the existing Bash recall logic SHALL also proceed (commit context may trigger relevant recall)
