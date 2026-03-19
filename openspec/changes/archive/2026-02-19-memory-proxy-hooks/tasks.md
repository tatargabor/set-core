## 1. Unified Handler

- [x] 1.1 Create `bin/wt-hook-memory` with event dispatching (`case "$1" in SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|PostToolUseFailure|SubagentStop|Stop`)
- [x] 1.2 Implement shared health check (single `set-memory health` at top, exit 0 if unhealthy)
- [x] 1.3 Implement session dedup cache (read/write `/tmp/set-memory-session-<ID>.json`, use session_id from input JSON, key = hash of event+tool+query, clear only on source=startup|clear)
- [x] 1.4 Implement shared proactive-and-format function (call `set-memory proactive`, filter by relevance 0.3, format as bullet list, output additionalContext JSON)
- [x] 1.5 Implement tool-specific query extraction (Read/Edit/Write → file_path, Bash → command, Task → prompt, Grep → pattern)

## 2. Event Handlers

- [x] 2.1 Port SessionStart handler from `wt-hook-memory-warmstart` (proactive context using git changed files, clear dedup cache only on source=startup|clear)
- [x] 2.2 Port UserPromptSubmit handler from `wt-hook-memory-recall` (topic recall with fixed explore regex, remove MEMORY_COUNT==0 early exit bug)
- [x] 2.3 Implement PreToolUse handler (unconditional proactive for all 6 tool types, no pattern matching)
- [x] 2.4 Implement PostToolUse handler (proactive using tool_input, --limit 2, dedup-checked)
- [x] 2.4a Implement PostToolUse:Edit/Write FileAccess memory creation (`set-memory remember --type Context --tags file-access`)
- [x] 2.4b Implement PostToolUse:Bash error pattern storage (detect error/warning in output → `set-memory remember --type Learning --tags error,bash`)
- [x] 2.5 Port PostToolUseFailure handler from `wt-hook-memory-posttool` (error recall + auto-promote)
- [x] 2.6 Implement SubagentStop handler (read agent_transcript_path last entries, use as proactive query)
- [x] 2.7 Port Stop handler from `wt-hook-memory-save` (transcript extraction + memory save, clean up dedup cache)

## 3. MCP Server

- [x] 3.1 Create `bin/set-memory-mcp-server.py` with Python MCP SDK (stdio transport, tool definitions)
- [x] 3.2 Implement core tools: remember, recall, proactive_context, forget, forget_by_tags, list_memories, get_memory, context_summary, brain, memory_stats (shell out to `set-memory` CLI)
- [x] 3.3 Implement maintenance tools: health, audit, cleanup, dedup
- [x] 3.4 Implement sync tools: sync, sync_push, sync_pull, sync_status
- [x] 3.5 Implement export/import tools: export_memories, import_memories

## 4. Hook Deployment

- [x] 4.1 Update `wt-deploy-hooks` hook_json template with full config (PreToolUse × 6 tools, PostToolUse × 6 tools, SubagentStop, all via `wt-hook-memory <EventName>`, event-specific timeouts: Stop=30s, UserPromptSubmit=15s, SessionStart=10s, rest=5s)
- [x] 4.2 Update `wt-deploy-hooks` upgrade paths (detect old individual scripts, replace with unified handler)
- [x] 4.3 Update `wt-deploy-hooks` hook_json_no_memory template (base-only, no memory hooks)

## 5. Backward Compatibility

- [x] 5.1 Convert `wt-hook-memory-warmstart` to thin wrapper: `exec wt-hook-memory SessionStart`
- [x] 5.2 Convert `wt-hook-memory-recall` to thin wrapper: `exec wt-hook-memory UserPromptSubmit`
- [x] 5.3 Convert `wt-hook-memory-pretool` to thin wrapper: `exec wt-hook-memory PreToolUse`
- [x] 5.4 Convert `wt-hook-memory-posttool` to thin wrapper: `exec wt-hook-memory PostToolUseFailure`
- [x] 5.5 Convert `wt-hook-memory-save` to thin wrapper: `exec wt-hook-memory Stop`

## 6. Project Init & MCP Registration

- [x] 6.1 Add MCP registration to `set-project init` (`claude mcp add set-memory -- python <path>/set-memory-mcp-server.py`, skip if already registered)
- [x] 6.2 Add MCP check function (parse `claude mcp list` output for `set-memory`)

## 7. CLAUDE.md and SKILL.md Updates

- [x] 7.1 Update `set-project` CLAUDE.md template with hook + MCP instructions (automatic hooks + active MCP tools, reference system-reminder labels)
- [x] 7.2 Update set-core CLAUDE.md with the same hook + MCP instructions
- [x] 7.3 Add "Check memory first" section to explore SKILL.md (before "Check for context", summarize known memory before independent exploration)

## 8. Cleanup Old References

- [x] 8.1 Add cleanup logic to `set-project init`: remove `<!-- set-memory hooks -->` blocks (all variants) from `.claude/skills/` SKILL.md files
- [x] 8.2 Add cleanup logic to `set-project init`: remove manual `set-memory recall`/`set-memory remember` instructions from `.claude/commands/` .md files
- [x] 8.3 Add cleanup logic to `set-project init`: delete `.claude/hot-topics.json` if it exists
- [x] 8.4 Remove hot-topics.json discovery logic from unified handler (no `discover_hot_topics()`)
- [x] 8.5 Remove hot-topics.json cache file references from pretool logic
- [x] 8.6 Update settings.json in set-core itself with the full hook config
