## Why

The hook-driven memory system (shodh-memory + wt-deploy-hooks) has replaced the deprecated `wt-memory-hooks install` workflow. SYN-06 benchmark confirms +34% quality, -20% tokens. However there is no migration guide for existing users, no CHANGELOG documenting breaking changes, the README "Latest update" date is stale (2026-02-17), and deprecated specs/tools need a clear sunset plan. Before tagging a release, we need documentation consistency and a migration path.

## What Changes

- **BREAKING**: Document that `wt-memory-hooks install` is fully deprecated — users must run `wt-deploy-hooks` instead
- Add a `MIGRATION.md` guide for users on pre-hook-driven versions (what to run, what changed, how to verify)
- Update README "Latest update" date and verify all sections reflect current architecture
- Review `install.sh` messaging — ensure it warns if legacy inline hooks are detected and offers cleanup
- Audit skill SKILL.md files for stale memory references (manual `wt-memory recall` instructions that are now handled by hooks)
- Clean up deprecated OpenSpec specs: mark `memory-hooks-cli` and `memory-hooks-gui` with sunset timeline
- Verify CLI `--help` text consistency across `wt-memory`, `wt-deploy-hooks`, `wt-project`

## Capabilities

### New Capabilities
- `release-migration-guide`: Migration documentation for users upgrading from legacy wt-memory-hooks to hook-driven memory

### Modified Capabilities
- `developer-memory-docs`: Update to include migration section and post-SYN-06 architecture summary
- `hook-driven-memory`: Add deprecation timeline for legacy tools, document install.sh detection behavior

## Impact

- `MIGRATION.md` (new file)
- `README.md` (date + section review)
- `docs/developer-memory.md` (migration section)
- `install.sh` (legacy hook detection warning)
- `.claude/skills/*/SKILL.md` (audit for stale manual recall)
- `openspec/specs/memory-hooks-cli/spec.md` and `memory-hooks-gui/spec.md` (sunset timeline)
- `bin/wt-memory --help`, `bin/wt-deploy-hooks --help`, `bin/wt-project --help` (consistency check)
