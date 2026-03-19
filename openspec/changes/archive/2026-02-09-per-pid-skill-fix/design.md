## Context

The multi-agent-gui change introduced per-PID skill tracking: each Claude agent writes its skill to `.set-core/agents/<pid>.skill`. However, the legacy `current_skill` file remains as a fallback — when per-PID files don't exist, `get_agent_skill()` falls back to the shared file. In multi-agent scenarios this means all agents show the same (last-written) skill.

Additionally, `wt-skill-start` is called via an LLM instruction in each SKILL.md prompt ("First, register this skill..."). The LLM may skip this, leaving no per-PID file at all. The `wt-hook-stop` Stop hook refreshes timestamps but doesn't register skills.

## Goals / Non-Goals

**Goals:**
- Per-PID skill files are the sole source of truth for skill display
- Skill registration happens automatically via Claude Code hook, not LLM instruction
- Multi-agent worktrees show independent, correct skill names per agent

**Non-Goals:**
- Changing the skill file format (name|timestamp)
- Changing the 30-minute staleness threshold
- Modifying how `detect_agents()` finds PIDs (that works correctly)

## Decisions

### Decision 1: Convert skill registration to a UserPromptSubmit hook

**Choice**: Add a `UserPromptSubmit` hook in `.claude/settings.json`. The hook script extracts the skill name from the user's prompt text (e.g. `/opsx:explore ...` → `opsx:explore`) and calls `wt-skill-start`.

**Why not keep LLM instruction**: The LLM may not execute the bash command (as observed — explore mode didn't register its skill). A hook fires automatically on every user prompt.

**Why not PreToolUse/Skill**: Claude Code does NOT fire PreToolUse events for the Skill tool — only for: Bash, Edit, Write, Read, Glob, Grep, Task, WebFetch, WebSearch, and MCP tools. PreToolUse/Skill hooks are silently ignored.

**Why UserPromptSubmit**: Users invoke skills via `/skill-name` syntax in their prompt. UserPromptSubmit fires on every prompt, and the hook extracts the `/name` pattern via regex. This works for all skills without per-skill configuration.

### Decision 2: Remove legacy current_skill entirely

**Choice**: Remove all reads/writes of `.set-core/current_skill`. The `get_agent_skill()` function only checks `.set-core/agents/<pid>.skill`.

**Why**: The legacy file is inherently single-agent. Keeping it as fallback causes incorrect display in multi-agent scenarios — exactly the bug we're fixing.

**Migration**: No migration needed — if per-PID file doesn't exist, agent simply shows no skill (correct behavior for agents that haven't invoked a skill yet).

### Decision 3: Remove manual wt-skill-start instructions from SKILL.md files

**Choice**: Remove the "First, register this skill" code block from all SKILL.md files since the hook handles it automatically.

**Why**: Redundant — the hook fires before the SKILL.md content is even processed. Keeping the instruction is confusing and may cause double-writes.

### Decision 4: Hook script reads skill name from user prompt text

**Choice**: The UserPromptSubmit hook receives JSON on stdin with a `prompt` field. Parse the prompt text for a leading `/skill-name` pattern (regex `^/(\S+)`), then call `wt-skill-start <skill-name>`.

The hook stdin format for UserPromptSubmit:
```json
{"prompt": "/opsx:explore multi-agent GUI fix", "session_id": "...", ...}
```

Non-skill prompts (no leading `/`) are silently ignored — the hook exits immediately.

### Decision 5: Only match leading `/skill-name`, not all occurrences

**Choice**: The regex `^/(\S+)` only matches the first `/skill-name` at the start of the prompt. Mid-text references like "run /opsx:verify next" are ignored.

**Why**: In Claude Code, only a leading `/` triggers a skill invocation. Mid-text `/` references are prose, not invocations. Multiple skill invocations per prompt don't happen — Claude Code parses the first `/command` and passes the rest as arguments.

**Known limitation**: If the user writes "futasd le a /opsx:verify-t" (skill name mid-sentence), the hook won't catch it. Claude may still invoke the Skill tool, but we can't hook into that (PreToolUse doesn't fire for Skill). This is an acceptable gap — the vast majority of skill invocations use leading `/` syntax.

## Risks / Trade-offs

- **Hook availability** → Only works in projects with `.claude/settings.json` configured. Not a risk for set-core (already has hooks), but limits portability. Mitigated by: `install.sh` deploys hooks to all managed projects.
- **Skill name extraction** → Requires parsing JSON in bash. Mitigated by: simple `jq` or `python3 -c` one-liner, both available on macOS.
- **Stale current_skill files** → Existing files in worktrees won't be auto-deleted. Mitigated by: harmless — nobody reads them after this change.
- **Indirect skill invocations** → If the user doesn't use `/` syntax but Claude auto-invokes a skill, the hook won't register it. Accepted trade-off — no hook mechanism exists for Skill tool invocations.
