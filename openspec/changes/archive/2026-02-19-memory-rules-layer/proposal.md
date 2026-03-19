## Why

The shodh-memory semantic recall system is probabilistic — high-stakes operational constraints (SQL credentials, mandatory pre-checks, hard deployment gates) can fail to surface or be silently ignored by agents. The current cheat-sheet tag is the only "emphasis" mechanism but it still goes through relevance filtering and is only loaded at session start. Agents end up trial-and-erroring with wrong passwords instead of using the correct one on the first attempt.

## What Changes

- New `.claude/rules.yaml` file format for storing deterministic, topic-matched operational rules
- `set-memory rules` CLI subcommand (`add`, `list`, `remove`) for managing rules
- `wt-hook-memory` extended to inject a `MANDATORY RULES` section before PROJECT MEMORY in UserPromptSubmit output — bypassing semantic filtering entirely
- Rules are topic-matched via simple keyword overlap (no embeddings), git-versioned, zero shodh-memory dependency
- Cheat-sheet tag role clarified: soft conventions/patterns only (not credentials or hard constraints)

## Capabilities

### New Capabilities
- `memory-rules`: Deterministic rules layer — `.claude/rules.yaml` file format, `set-memory rules` CLI, and hook injection of `MANDATORY RULES` section in UserPromptSubmit context

### Modified Capabilities
- `cheat-sheet-curation`: Role clarification — cheat-sheet is for emergent soft conventions; hard constraints belong in rules. Docs and L5 extraction prompt updated accordingly.

## Impact

- `bin/wt-hook-memory` — UserPromptSubmit handler extended to read and inject rules
- `bin/set-memory` — new `rules` subcommand (add/list/remove)
- `.claude/rules.yaml` — new per-project file (created by CLI, gitignored or committed per user preference)
- `docs/developer-memory.md` — new Rules section, cheat-sheet role update
- No shodh-memory changes required
- No breaking changes to existing memory types or hook behavior
