## Requirements

### Requirement: Automatic memory save after git commit
When `handle_post_tool()` receives a Bash tool event and the command matches `git commit`, it SHALL extract the commit message and save a Learning memory with the format: `Committed: <commit_message>`. Tags SHALL include `phase:commit-save,source:hook`.

#### Scenario: Heredoc commit message
- **WHEN** PostToolUse fires for Bash tool with command containing `git commit -m "$(cat <<'EOF'\nfix: add checkpoint saves\nEOF\n)"`
- **THEN** a Learning memory SHALL be saved: `Committed: fix: add checkpoint saves`

#### Scenario: Simple -m commit message
- **WHEN** PostToolUse fires for Bash tool with command containing `git commit -m "fix: add checkpoint saves"`
- **THEN** a Learning memory SHALL be saved: `Committed: fix: add checkpoint saves`

#### Scenario: Fallback to description field
- **WHEN** PostToolUse fires for Bash tool with a git commit command whose message cannot be parsed
- **AND** the tool_input contains a `description` field
- **THEN** the description SHALL be used as fallback content

#### Scenario: Bash command without git commit
- **WHEN** PostToolUse fires for Bash tool with command `ls -la src/`
- **THEN** no commit-save SHALL execute
- **AND** the existing Bash recall logic SHALL proceed normally

### Requirement: Commit-save dedup by content
Commit saves SHALL be deduplicated by content per session. The dedup key format SHALL be `WriteSave:commit:<save_content>`.

#### Scenario: Same commit saved twice
- **WHEN** a git commit fires twice with the same message in one session
- **THEN** only the first SHALL be saved

### Requirement: Commit-save does not block recall
After performing a commit-save (or skipping due to dedup), the handler SHALL continue with normal PostToolUse Bash recall logic. Commit context may trigger relevant memory recall.

### Requirement: No Write/Edit PostToolUse hooks
Write and Edit tool events SHALL NOT trigger the PostToolUse memory hook. Only Read and Bash matchers SHALL be deployed. Write/Edit saves were removed because they produced low-value noise (bare filepaths without context).
