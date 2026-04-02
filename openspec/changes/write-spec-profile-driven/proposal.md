## Why

Spec quality directly determines orchestration success. Runs with modular specs (WHEN/THEN scenarios, structured seed data, per-feature files) achieve near-100% merge rate. Runs with flat prose specs (code blocks in requirements, no scenarios, file paths hardcoded) consistently get stuck at integration gates. The write-spec skill currently produces flat prose regardless of project type, missing critical web-specific sections (Prisma seed, per-feature files, wireframes, test strategy). The decomposer has to parse prose to extract requirements — error-prone and lossy.

## What Changes

- **Profile-driven spec sections**: Add `spec_sections()` method to `ProjectType` ABC. Web module implements web-specific sections (data model, seed catalog, per-feature specs, wireframes, test strategy, design mapping).
- **Modular output**: write-spec generates modular structure: `docs/spec.md` (main) + `docs/features/*.md` (per-feature) + `docs/catalog/*.md` (seed data for web).
- **Anti-pattern detection**: Before assembly, warn about code blocks, file paths, missing scenarios, placeholder seed data in the spec.
- **REQ-ID + Scenario enforcement**: Every requirement gets an explicit REQ-ID. Every requirement must have at least one WHEN/THEN scenario. Assembly blocks if requirements lack scenarios.
- **Orchestrator directives section**: write-spec adds a `## Orchestrator Directives` yaml block to the spec (max_parallel, review gates, e2e mode).
- **Verification checklist**: Auto-generate a verification checklist section from requirements.

## Capabilities

### New Capabilities
- `spec-writing-profiles` — Profile-driven spec section generation with project-type templates

### Modified Capabilities
_(none — write-spec skill is not currently spec'd, this creates the first spec for it)_

## Impact

- **lib/set_orch/profile_types.py**: New `spec_sections()` ABC method
- **modules/web/set_project_web/project_type.py**: Web-specific spec sections implementation
- **.claude/skills/set/write-spec/SKILL.md**: Major rewrite — profile-driven, modular output, anti-pattern gate
- **docs/guide/writing-specs.md**: Update with new structure and examples
