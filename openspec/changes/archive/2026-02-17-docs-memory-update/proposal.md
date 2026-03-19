## Why

Three recently completed changes need documentation: (1) `memory-dedup-audit` added `set-memory audit` and `set-memory dedup` commands, (2) `save-hook-staging` added a staging pattern to transcript extraction, and (3) `set-project-init-deploy` enhanced `set-project init` to deploy hooks+commands+skills per-project. None of these are documented yet.

Additionally, the GUI now shows `[M]`, `[O]`, and `[R]` status badges — a new screenshot captures this. The Setup section lacks step-by-step happy-flow guides. And there's no explanation of how set-memory differs from Claude Code's built-in memory system (CLAUDE.md + auto memory), which is a common source of confusion for new users.

## What Changes

- Add `set-memory audit` and `set-memory dedup` to the CLI Reference in `docs/developer-memory.md` (Diagnostics section) and `README.md` (Developer Memory CLI table)
- Add happy-flow command sequences to `docs/developer-memory.md` Setup section: (A) fresh project init with OpenSpec + memory, (B) adding memory to existing OpenSpec project, (C) re-installing hooks after `wt-openspec update`. Flows now use `set-project init` (which deploys hooks+commands+skills) instead of separate `wt-deploy-hooks`
- Add new screenshot (`docs/images/control-center-memory.png`) showing M/O/R badges, reference it in `docs/developer-memory.md` GUI section
- Update `docs/readme-guide.md` mandatory CLI list to include `audit` and `dedup`
- Document the staging pattern (from `save-hook-staging`) in the automatic hooks section of `developer-memory.md`
- Add "How set-memory differs from Claude Code's built-in memory" section to `developer-memory.md` — explaining complementary roles (instructions vs experience), search vs load, worktree sharing, structured types, team sync
- Update `README.md` Quick Start and CLI Reference to reflect new `set-project init` behavior (now deploys hooks+commands+skills, not just registers)

## Capabilities

### New Capabilities

(none — purely documentation updates)

### Modified Capabilities

- `developer-memory-docs`: Adding audit/dedup CLI docs, happy-flow setup guides, screenshot, staging pattern docs, and Claude Code memory comparison section

## Impact

- `docs/developer-memory.md`: CLI Reference table, Setup section (happy flows), GUI section (screenshot), Automatic hooks section (staging), new comparison section
- `docs/readme-guide.md`: CLI documentation rules (mandatory command list)
- `README.md`: Developer Memory CLI table (audit/dedup rows), Quick Start (`set-project init` description update), CLI Reference (`set-project` description update)
- `docs/images/control-center-memory.png`: New screenshot file (user-provided)
- No code changes — documentation only
