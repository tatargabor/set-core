# memory-hooks-gui Specification (ARCHIVED)

## Purpose
**ARCHIVED** — The "Install/Reinstall Memory Hooks" GUI actions have been removed. The 5-layer hook system in `settings.json` is automatically deployed by `set-project init` and requires no GUI interaction.

## REMOVED Requirements

### Requirement: Install Memory Hooks action in Memory submenu
**Reason**: DEPRECATED — The "Install/Reinstall Memory Hooks" GUI actions have been removed. The 5-layer hook system in `settings.json` is automatically deployed by `set-project init` and requires no GUI interaction.
**Migration**: Hooks are deployed automatically. No GUI action needed.

### Requirement: Auto-reinstall hooks after OpenSpec update
**Reason**: DEPRECATED — Hooks are in `settings.json`, not in SKILL.md files, so OpenSpec updates don't affect them.
**Migration**: No action needed.

### Requirement: Hook status in FeatureWorker cache
**Reason**: DEPRECATED — The `_poll_memory_hooks` feature worker check has been removed. Hook deployment is managed by `set-project init`.
**Migration**: Hook status is implicit — if `set-project init` was run, hooks are deployed.
