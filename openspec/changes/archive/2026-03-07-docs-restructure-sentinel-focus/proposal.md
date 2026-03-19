## Why

The README is 867 lines and tries to be everything: landing page, tutorial, CLI reference, architecture doc, and use case gallery. Nobody reads it end-to-end. The narrative centers on the Control Center GUI ("I kept losing track of terminal tabs") when the actual value proposition has shifted to sentinel-driven autonomous orchestration ("give it a spec, get merged features"). The `docs/readme-guide.md` enforces a rigid 16-section structure that perpetuates this bloat. Sub-features like Developer Memory, Team Sync, and Orchestration deserve their own pages but are crammed into README sections.

The docs need to be restructured: short README as landing page, dedicated sub-pages per feature group, sentinel/orchestration as the lead narrative, and a plugin section for future extensibility. The system should be reproducible — clear enough that the README can be regenerated from the guide + sub-pages.

## What Changes

- **README.md**: Rewrite from 867 lines to ~150-200 lines. Sentinel-first narrative. Features get 1-2 sentences each with links to dedicated docs.
- **docs/readme-guide.md**: Replace the 16-section rigid structure with a new guide matching the short README format. Fewer mandatory sections, clear "what goes where" rules.
- **New doc pages**: Split out feature groups into dedicated pages (worktrees, ralph, gui, team-sync, mcp-server, plugins, cli-reference, configuration, architecture, getting-started).
- **Existing docs consolidation**: `agent-messaging.md` content merges into `team-sync.md`. `config.md` evolves into a proper configuration reference.
- **Plugin placeholder**: New `docs/plugins.md` with plugin concept, installation pattern, and registry placeholder for plugins in separate repos.
- **Architecture simplification**: The current 4-layer ASCII diagram in README replaced by a simple sentinel-centric diagram. Full architecture moves to `docs/architecture.md`.

## Capabilities

### New Capabilities
- `docs-structure`: The overall documentation site structure — which pages exist, what goes where, navigation between pages, and the generation/update workflow.
- `docs-readme`: The README.md content, format, and generation rules — the landing page that replaces the current monolithic README.
- `docs-feature-pages`: Individual feature documentation pages — worktrees, ralph, gui, team-sync, mcp-server, plugins, cli-reference, configuration, architecture, getting-started.

### Modified Capabilities
<!-- No existing specs are being modified — this is a docs-only change -->

## Impact

- **Files changed**: `README.md`, `docs/readme-guide.md`, multiple new files in `docs/`
- **Files removed**: None (existing docs are consolidated, not deleted — old files can be removed after content is migrated)
- **No code changes**: This is purely documentation restructuring
- **Consumer projects**: No impact — `set-project init` deploys `.claude/` files, not docs
- **External links**: Any external links pointing to README sections will break (acceptable — the README was not stable anyway)
