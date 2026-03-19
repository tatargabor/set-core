## REMOVED Requirements

### Requirement: set-memory-hooks install command
**Reason**: DEPRECATED — The 5-layer hook system in `settings.json` (deployed by `wt-deploy-hooks` via `set-project init`) now handles all memory operations. Inline SKILL.md patching is no longer needed.
**Migration**: Use `set-project init` to deploy hooks. The `check` and `remove` subcommands still exist for legacy cleanup.

### Requirement: Hook content and placement
**Reason**: DEPRECATED — Memory hooks are now in `settings.json` event handlers, not inline in SKILL.md files.
**Migration**: Hooks are automatically deployed by `wt-deploy-hooks`.

### Requirement: set-memory-hooks check command
**Reason**: DEPRECATED — Hook status is managed by `wt-deploy-hooks` and `set-project init`.
**Migration**: Run `set-project init` to ensure hooks are deployed.

### Requirement: set-memory-hooks remove command
**Reason**: DEPRECATED — Still functional for removing legacy inline hooks from SKILL.md files.
**Migration**: Run `set-memory-hooks remove` to clean up, then `set-project init` to deploy the new hook system.
