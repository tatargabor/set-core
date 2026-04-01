# Design: spec-writing-skill

## Decisions

### D1: Skill, not CLI tool
This is an interactive workflow that needs LLM reasoning (understanding project context, asking good questions, generating structured text). A skill is the right abstraction — it runs inside Claude Code with full context.

### D2: Guide content embedded in SKILL.md, not deployed as rule
The 543-line writing-specs.md guide is reference material for the skill, not a rule for everyday agent work. Deploying it as a rule would add ~2K tokens to every agent's context. Instead, the skill reads it when invoked.

### D3: Section-by-section workflow with skip logic
The skill doesn't ask all questions upfront. It goes section by section, detects what it can from the codebase, and only asks when it needs user input. If prisma schema exists → pre-populate data model. If .make exists → auto-detect design. If package.json has next-intl → pre-populate i18n.

### D4: Output is a single spec.md, not multiple files
The spec is one file. The orchestration decomposer handles splitting it into changes. Users can optionally split into docs/features/*.md — but the skill produces one file by default.

## File Map

| File | Action | Description |
|------|--------|-------------|
| `.claude/skills/set/write-spec/SKILL.md` | New | Interactive spec-writing skill |
| `.claude/commands/set/write-spec.md` | New | Command trigger |
