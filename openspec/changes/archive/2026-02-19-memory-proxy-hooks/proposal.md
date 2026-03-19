## Why

Memory hooks fire selectively (pattern-matched PreToolUse, no PostToolUse), so memory context is only injected at session start and on prompt submit. The agent receives 1-2 memory injections then "forgets" as it dives into file reads and code exploration.

The upstream shodh-memory project uses a **two-layer integration**: (1) hooks on ALL tool events for passive injection, and (2) an **MCP server** giving the LLM 15 active memory tools (remember, recall, proactive_context, etc.). This creates continuous, bidirectional memory that the agent cannot ignore.

We need to adopt this exact pattern — hooks + MCP — modeled point-by-point after the shodh implementation.

## What Changes

### Layer 1: Hooks (passive — inject memory into every tool interaction)
- **Replace 5 separate hook scripts** with a **single unified handler** (`wt-hook-memory`) dispatching by event type
- **Add PostToolUse hooks** for Read, Edit, Write, Bash, Task — memory AFTER every tool call
- **Add SubagentStop hook** — memory when subagents complete
- **Remove hot-topic pattern matching** — every tool call gets memory unconditionally
- **Session-level dedup cache** — prevent redundant recalls within a session

### Layer 2: MCP server (active — LLM can call memory tools directly)
- **Build own MCP server wrapping `set-memory` CLI** — same pattern as shodh's MCP, but calls our commands
- **LLM gets ~20 tools**: remember, recall, proactive_context, forget, list, stats, brain, sync, export, etc.
- **Shell-out to `set-memory`** — all custom logic (branch boosting, auto-tag, dedup) applies to MCP calls too
- **Single path**: both hooks and MCP go through `set-memory` → PyO3 → shodh Rust

### Layer 3: Cleanup and deployment
- **Update CLAUDE.md** — explicit memory-use instructions (system-reminders + MCP tools)
- **Update SKILL.md** (explore, apply, etc.) — "check memory first" steps
- **Clean up old references** — remove deprecated set-memory inline instructions from all .md files
- **Update `wt-deploy-hooks`** — full hook config including PostToolUse/SubagentStop
- **Update `set-project init`** — deploy hooks + CLAUDE.md + MCP registration

### Shodh source analysis (reference implementation)
- **hooks/memory-hook.ts** — single TypeScript handler, 6 events, all dispatched to REST :3030
- **hooks/claude-settings.json** — full hook configuration template
- **mcp-server/index.ts** — MCP server exposing 37 tools (we replicate the pattern, wrapping set-memory instead)
- **src/handlers/recall.rs** — proactive_context engine (parallel semantic+graph+todo+fact)
- **src/python.rs** — PyO3 FFI bindings (Python calls Rust directly, no HTTP)

## Capabilities

### New Capabilities
- `posttool-memory-surfacing`: PostToolUse memory injection for Read, Edit, Write, Bash, Task
- `unified-memory-hook`: Single handler replacing 5 scripts, session dedup cache
- `mcp-memory-tools`: Own MCP server wrapping full set-memory CLI, giving LLM ~20 active memory tools

### Modified Capabilities
- `hook-driven-memory`: Hooks cover all 7 events (was 5), unified handler, stronger CLAUDE.md
- `hot-topic-recall`: Pattern matching removed — unconditional recall
- `project-init-deploy`: Deploy hooks + CLAUDE.md + MCP registration + cleanup old .md references

## Impact

- **Hook scripts**: 5 → 1 unified `bin/wt-hook-memory`
- **MCP**: Own `set-memory-mcp` server wrapping full set-memory CLI
- **settings.json**: PostToolUse (6 tools), SubagentStop, all via unified handler
- **wt-deploy-hooks**: Template with full config
- **set-project init**: Hooks + CLAUDE.md + MCP + cleanup
- **CLAUDE.md**: Rewritten with hook + MCP instructions
- **All SKILL.md/command .md files**: Old set-memory references cleaned
