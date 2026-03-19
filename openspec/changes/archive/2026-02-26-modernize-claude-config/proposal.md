## Why

Claude Code now supports `.claude/rules/` (path-scoped auto-loaded rules), `.claude/agents/` (custom subagents with tool restrictions, model selection, persistent memory), skill frontmatter options (`context: fork`, `disable-model-invocation`), and `@path` imports in CLAUDE.md. This project uses none of these features — all project instructions live in a monolithic CLAUDE.md, there are no custom subagents, and GUI-specific rules consume context even when working on non-GUI code. Adopting these patterns will reduce context waste, enable specialized AI workers, and make the configuration more maintainable.

**Constraint**: The existing memory hook system (7 hook events in `.claude/settings.json` calling `wt-hook-memory`, `wt-hook-skill`, `wt-hook-activity`, `wt-hook-stop`) and the Persistent Memory CLAUDE.md section (managed by `set-project init`) must remain untouched.

## What Changes

- **Create `.claude/rules/` directory** with path-scoped topic rules extracted from CLAUDE.md (GUI dialogs, GUI testing, GUI startup/debug, OpenSpec artifacts, README updates)
- **Create `.claude/agents/` directory** with custom subagents (code-reviewer, gui-tester, openspec-verifier)
- **Slim down CLAUDE.md** — move reference content to rules, keep only universal "always do X" directives and quick-reference commands; add `@path` imports where appropriate
- **Add compact instructions** to CLAUDE.md so context compaction preserves critical state
- **Optimize skill frontmatter** — add `context: fork` to exploration-heavy skills, `disable-model-invocation: true` to rarely-invoked skills
- **Add `SubagentStart` hook** to inject project memory context into spawned subagents
- **Add `SessionStart[compact]` hook** to re-inject critical context after auto-compaction
- **Update `set-project init`** to deploy rules/ and agents/ alongside existing CLAUDE.md deployment

## Capabilities

### New Capabilities
- `path-scoped-rules`: Path-filtered `.claude/rules/*.md` files that load only when working on matching files (GUI rules only for `gui/**`, OpenSpec rules only for `openspec/**`)
- `custom-subagents`: Specialized AI worker definitions in `.claude/agents/` with tool restrictions, model selection, and task-specific prompts
- `context-preservation`: Compact instructions in CLAUDE.md and SessionStart[compact] hook to preserve critical state through context compaction
- `subagent-context-injection`: SubagentStart hook that injects project memory context into spawned subagents

### Modified Capabilities
- `project-init-deploy`: set-project init must deploy rules/ and agents/ directories alongside CLAUDE.md to target projects

## Impact

- `.claude/rules/` — 5-6 new .md files with YAML frontmatter path scoping
- `.claude/agents/` — 3 new .md agent definitions
- `CLAUDE.md` — significant content reduction (from ~144 lines to ~60-70 lines)
- `.claude/settings.json` — 2 new hook entries (SubagentStart, SessionStart[compact]) added alongside existing memory hooks (existing hooks untouched)
- `.claude/skills/openspec-*/SKILL.md` — frontmatter additions (context, disable-model-invocation)
- `lib/` or `bin/` — set-project init updated to deploy new directories
- No changes to: memory hooks, memory MCP tools, skill command files, hook scripts
