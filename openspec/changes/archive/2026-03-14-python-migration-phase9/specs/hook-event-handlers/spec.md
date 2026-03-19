## Purpose

Migrate `lib/hooks/events.sh` (727 LOC) to `lib/set_hooks/events.py`. The main event dispatcher for Claude Code hooks: SessionStart, UserPromptSubmit, PostToolUse, PreToolUse. Each event triggers memory recall, context injection, and metrics collection.

## Requirements

### EVENTS-01: Event Dispatch
- `handle_event(event_type, input_file)` main entry point
- Route to: `handle_session_start()`, `handle_user_prompt()`, `handle_post_tool()`, `handle_pre_tool()`
- Read input JSON from `input_file` (Claude Code hook protocol)
- Write output to stdout (injected into Claude context)

### EVENTS-02: SessionStart Handler
- Clear dedup cache on new session or `/clear`
- Recall cheat sheet memories (tag: `cheat-sheet`, limit: 5)
- Recall project context memories (proactive context based on project)
- Format output: `=== OPERATIONAL CHEAT SHEET ===` + `=== PROJECT CONTEXT ===`

### EVENTS-03: UserPromptSubmit Handler
- Extract user prompt text from input JSON
- Run topic-based memory recall (proactive context on prompt content)
- Match rules.yaml patterns against prompt
- Format output: `=== PROJECT MEMORY ===` with relevant memories
- Dedup: skip memories already surfaced this session (via content hash)

### EVENTS-04: PostToolUse Handler
- Detect tool type and result from input JSON
- For file reads: recall memories related to the file path
- For bash commands: recall memories related to the command/error
- For errors: surface past fixes matching the error pattern
- Commit-based save: if tool was a git commit, extract and save insight
- Format output: `=== MEMORY: Context for this file/command ===`

### EVENTS-05: Frustration Detection
- Scan user prompt for frustration signals (exclamation marks, specific patterns)
- On detection: save frustration memory with severity level
- Adjust recall aggressiveness based on frustration level

### EVENTS-06: Unit Tests
- Test event routing with mock input files
- Test SessionStart output format
- Test UserPromptSubmit with various prompt types
- Test PostToolUse with file read, bash error, git commit inputs
- Test frustration detection patterns
