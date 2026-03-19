## Context

shodh-memory (Rust-based) accepts `memory_type` as a string but only maps 3 values to distinct `experience_type` enum variants: `Decision`, `Learning`, `Context`. All other strings (including `Observation`, `Event`) silently fall back to `Context`. Our codebase uses `Observation` and `Event` extensively in hooks, CLAUDE.md, and GUI.

## Goals / Non-Goals

**Goals:**
- All memory saves use valid shodh-memory types
- CLI provides safety net mapping for backward compatibility
- Docs and hooks reflect the correct 3-type system
- README documents Developer Memory as an experimental feature
- readme-guide includes memory in mandatory Features section

**Non-Goals:**
- Extending shodh-memory itself to support more types
- Migrating existing memories with wrong experience_type
- Full memory user guide (just feature overview + CLI reference)

## Decisions

### Decision 1: Map in set-memory CLI (defense in depth)

Add a mapping step in `cmd_remember` before passing to Python:
- `Observation` → `Learning` (observations are learnings about the system)
- `Event` → `Context` (events are contextual records)

Print a warning to stderr when mapping occurs so callers know. The `|| true` at the end of `run_shodh_python` already swallows errors, so stderr warnings are safe.

**Alternative**: Only fix the callers (hooks, CLAUDE.md) — rejected because any future caller could repeat the mistake.

### Decision 2: Fix all callers to use correct types directly

Even with CLI mapping, update hooks and docs to use the valid types. This makes the intent clear and avoids the stderr warning during normal operation.

### Decision 3: GUI shows only valid types

RememberNoteDialog combobox: `[Learning, Decision, Context]`. Remove Observation/Event since they were never correctly stored anyway. MemoryBrowseDialog badge colors: keep Decision (blue), Learning (green), Context (amber). Remove Observation/Event entries.

### Decision 4: README Developer Memory section — experimental badge

Developer Memory gets its own `### Developer Memory (Experimental)` subsection under Features, following the same pattern as Team Sync. Mark as experimental since shodh-memory is a third-party dependency and the feature is new.

CLI Reference gets `set-memory` and `set-memory-hooks` entries in a new "Developer Memory" category.

### Decision 5: readme-guide update — add memory to Features list

Add `**Developer Memory** — per-project remember/recall, OpenSpec hooks, GUI browse` to the Features section in `docs/readme-guide.md` so future README regenerations include it.

## Risks / Trade-offs

- **[Risk] Users have muscle memory for "Observation" type** → CLI mapping handles this gracefully with a warning
- **[Risk] Existing hooks in .claude/skills/ still have old types** → Must re-run `set-memory-hooks install` after update
- **[Risk] shodh-memory is third-party, could change types** → README marks feature as Experimental, CLI mapping provides buffer
