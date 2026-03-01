## ADDED Requirements

### Requirement: MIGRATION.md file exists
The project SHALL have a `MIGRATION.md` file at the repository root documenting the upgrade path from legacy `wt-memory-hooks install` to hook-driven memory via `wt-deploy-hooks`.

#### Scenario: File exists and is discoverable
- **WHEN** a user looks for migration instructions
- **THEN** `MIGRATION.md` exists at the repo root and is linked from README.md

### Requirement: Migration steps are complete and ordered
The migration guide SHALL include numbered steps covering: detecting legacy hooks, removing them, verifying new hooks are active, and confirming memory health.

#### Scenario: User follows migration steps
- **WHEN** a user with legacy inline hooks follows the migration guide
- **THEN** they run `wt-memory-hooks check` to detect, `wt-memory-hooks remove` to clean up, `wt-deploy-hooks .` to ensure new hooks, and `wt-memory health` to verify — all completing without errors

### Requirement: Before/after comparison
The migration guide SHALL include a before/after section showing what changed: old workflow (manual recall in SKILL.md) vs new workflow (automatic hook injection via settings.json).

#### Scenario: User understands the change
- **WHEN** a user reads the before/after section
- **THEN** they understand that memory recall/save is now automatic via hooks and no longer requires manual SKILL.md patching

### Requirement: Troubleshooting section
The migration guide SHALL include a troubleshooting section covering common issues: hooks not firing, memory not being recalled, stale inline hooks interfering.

#### Scenario: Hooks not firing after migration
- **WHEN** a user completes migration but hooks don't fire
- **THEN** the troubleshooting section tells them to check `wt-deploy-hooks --check .` and verify `.claude/settings.json` contains hook entries
