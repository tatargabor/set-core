# Proposal: design-brief-matcher

## Why

The `design_brief_for_dispatch()` function in bridge.sh uses exact substring matching to match page names from `design-brief.md` against change scope text. This means "Admin Products" only matches if the scope contains the literal substring "admin products". In practice, decompose generates scope descriptions like "admin product management CRUD table with sidebar navigation" which do NOT contain the exact page name — so the per-change design.md is empty and agents lose visual design context.

The sibling function `_dispatch_from_design_system()` already solves this with bidirectional matching, but `design_brief_for_dispatch()` was never upgraded.

Additionally, the hardcoded `_DESIGN_BRIEF_ALIASES` array contains project-specific page names (craftbrew). Per the modular architecture, project-specific aliases belong in scaffold-level files, not in the core bridge.sh.

## What Changes

- **Add stem-based bidirectional matching** to `design_brief_for_dispatch()`: if exact match fails and aliases don't match, check whether ALL words of the page name (stemmed to first 4 chars) appear in the scope text. This catches "Admin Products" for scope "admin product management" without false positives.
- **Move hardcoded aliases to scaffold files**: extract `_DESIGN_BRIEF_ALIASES` to per-scaffold alias files (e.g., `tests/e2e/scaffolds/craftbrew/docs/design-brief-aliases.txt`). The bridge.sh default array becomes empty.
- **Deploy alias files in runners**: runner scripts set `DESIGN_BRIEF_ALIASES_FILE` env var pointing to the scaffold's alias file before orchestration starts.
- **Create minishop alias file**: scaffold-specific aliases for minishop page names.

## Capabilities

### New Capabilities
- `design-brief-stem-match` — stem-based bidirectional page matching in design_brief_for_dispatch

### Modified Capabilities
- `design-dispatch-context` — alias externalization (move hardcoded aliases to scaffold files)

## Impact

- `lib/design/bridge.sh` — matcher logic + alias cleanup
- `tests/e2e/scaffolds/minishop/docs/design-brief-aliases.txt` — new file
- `tests/e2e/scaffolds/craftbrew/docs/design-brief-aliases.txt` — new file (extracted from hardcoded)
- `tests/e2e/runners/run-minishop.sh` — alias file env var
- `tests/e2e/runners/run-craftbrew.sh` — alias file env var
- No core Python changes, no module changes — pure shell + scaffold
