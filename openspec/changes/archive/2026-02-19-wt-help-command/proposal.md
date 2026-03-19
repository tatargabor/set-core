## Why

When users ask an LLM "how does set-memory work?" or "what does /opsx:apply do?", the LLM has no automatic way to find and present the answer. Documentation exists across SKILL.md files, docs/, CLI --help flags, and README.md — but nothing tells the LLM where to look. This creates a gap where the LLM either guesses or says "I don't know" about features it could easily explain.

## What Changes

- Add `.claude/commands/wt/help.md` — a quick reference command covering all CLI tools, skills, MCP tools, and common workflows. Auto-deploys to target projects via existing `set-project init` mechanism (no deployment changes needed).
- Add a "Help & Documentation" section to `CLAUDE.md` (~5-10 lines) — a help router that tells the LLM where to find answers when users ask about features.

## Capabilities

### New Capabilities
- `help-command`: The `/wt:help` slash command providing a quick reference for all set-core features (CLI commands, skills, MCP tools, workflows)
- `help-router`: CLAUDE.md section that routes LLM help queries to the right documentation sources

### Modified Capabilities

_(none — no existing spec requirements change)_

## Impact

- `.claude/commands/wt/help.md` — new file, auto-deployed by existing `deploy_set_tools()` in `bin/set-project`
- `CLAUDE.md` — small addition (~5-10 lines help router section)
- No code changes, no dependency changes, no API changes
