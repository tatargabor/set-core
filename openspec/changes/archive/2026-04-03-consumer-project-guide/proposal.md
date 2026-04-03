## Why

Consumer projects initialized with `set-project init` have no understanding of their own set-core structure. The deployed rules, commands, and conventions are present but undocumented — the project's Claude agent doesn't know what's managed by set-core vs. project-owned, how to add custom rules, or how to write OpenSpec changes that respect the framework conventions.

This was never a problem when set-core orchestrated pre-built projects. Now that projects build themselves incrementally (local agent sessions using `/opsx:*` for smaller changes, research, documentation), the agent needs a guide.

## What Changes

- **New core rule template** (`templates/core/rules/project-guide.md`) deployed as `set-project-guide.md` to all consumer projects
- Covers: file ownership (set-* vs custom), how to add project rules, how to extend conventions for domain-specific patterns (mobile, fintech, etc.), OpenSpec change guidelines, and config/knowledge file locations

## Capabilities

### New Capabilities
- `consumer-project-guide`: Rule template that teaches consumer project agents about set-core structure and conventions

### Modified Capabilities
- `project-init-deploy`: The new rule deploys via the existing core rules mechanism (no code change needed — just adding a file to `templates/core/rules/`)

## Impact

- All consumer projects get `set-project-guide.md` on next `set-project init`
- No code changes to deploy logic — the existing `templates/core/rules/` → `set-*` prefix mechanism handles it
- Existing projects unaffected until re-init
