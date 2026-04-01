# Proposal: spec-writing-skill

## Why

The `docs/guide/writing-specs.md` guide (543 lines) documents how to write good specs, but users can't easily use it during spec writing. They need an interactive skill that walks them through the process — asking questions, detecting project context, and generating a structured spec file. The guide exists as documentation; the skill makes it actionable.

Additionally, the design integration docs and the spec-writing guide need to be deployed to consumer projects so agents in those projects can reference them.

## What Changes

### New Skill: `/set:write-spec`
- Interactive spec-writing assistant that produces a structured spec file
- Reads project context (package.json, prisma schema, existing code, orchestration config)
- Asks targeted questions per section (data model, pages, design, auth, i18n, seed data)
- Generates `docs/spec.md` (or user-specified path) with all sections filled
- References `docs/guide/writing-specs.md` for conventions
- Integrates with `set-design-sync` if a `.make` file is present

### New Command: `/set:write-spec`
- Command definition that triggers the skill
- Brief usage instructions

### Template Deployment
- The `writing-specs.md` guide should be available in consumer projects as a reference
- Deploy to `.claude/rules/` as `spec-writing-guide.md` so agents can read it

## Capabilities

### New Capabilities
- `write-spec-skill`: Interactive spec generation from project context and user input

### Modified Capabilities
- `template-deployment`: Add spec-writing guide to deployed templates

## Impact
- **New files**: `.claude/skills/set/write-spec/SKILL.md`, `.claude/commands/set/write-spec.md`
- **Modified files**: `modules/web/set_project_web/templates/nextjs/manifest.yaml` (if adding guide to deployment)
- **Risk**: Low — new skill, doesn't change existing behavior
