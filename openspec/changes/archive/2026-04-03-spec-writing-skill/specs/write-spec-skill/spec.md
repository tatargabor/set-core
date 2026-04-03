# Spec: Write Spec Skill

## Status: new

## Requirements

### REQ-SKILL-INTERACTIVE: Interactive spec generation workflow
- The skill SHALL detect project context automatically: package.json (deps, name), prisma/schema.prisma (existing models), existing docs/*.md files, set/orchestration/config.yaml, .make files in docs/, pyproject.toml, Cargo.toml, go.mod, docker-compose.yml, Makefile, README.md
- The skill SHALL walk through spec sections in order: Project Overview → Tech Stack & Architecture → Data Model / State → Screens / Endpoints / CLI Commands → Component Behavior / Business Logic → Auth & Roles → Seed / Fixture Data → Design Integration → i18n → Testing Strategy
- For each section, the skill SHALL ask targeted questions using AskUserQuestion if the context is unclear
- The skill SHALL skip sections where project context provides enough information (e.g., if prisma schema exists, pre-populate data model)
- For **unknown or non-standard tech stacks**, the skill SHALL use Agent tool (Explore subagent) to research the project structure, read key files, and understand the architecture before asking questions
- The skill SHALL NOT assume web — if the project is a CLI tool, backend API, data pipeline, or other type, it SHALL adapt sections accordingly (e.g., "CLI Commands & Flags" instead of "Page Layouts", "API Endpoints" instead of "Screens")
- Output: structured markdown file at user-specified path (default: `docs/spec.md`)

### REQ-SKILL-DESIGN-DETECT: Auto-detect and integrate design sources
- If `docs/design.make` or `docs/*.make` exists, the skill SHALL suggest running `set-design-sync` and incorporate the generated `design-system.md` tokens into the spec
- If `docs/design-system.md` already exists, the skill SHALL read it and pre-populate the Design Tokens section
- If no design source exists, the skill SHALL ask: "Do you have a Figma design? (1) Yes, I'll export a .make file (2) No, I'll specify colors/fonts manually (3) No design — use framework defaults"

### REQ-SKILL-CONVENTIONS: Follow spec-writing conventions from guide
- The skill SHALL follow the conventions documented in `docs/guide/writing-specs.md`
- Key conventions: concrete layouts (not vague descriptions), exact hex colors, named entities with fields, explicit auth roles, realistic seed data names
- The skill SHALL include a "## Design Reference" section if design-system.md exists
- The skill SHALL warn about common mistakes (from the guide's Common Mistakes table)

### REQ-COMMAND: Slash command definition
- Create `.claude/commands/set/write-spec.md` with usage instructions
- The command SHALL trigger the write-spec skill

### REQ-RESEARCH: Use agents to explore unknown projects
- When the project type is unknown or uses unfamiliar tools/frameworks, the skill SHALL spawn an Explore agent to research the codebase structure, key files, and architecture patterns
- The skill SHALL NOT skip sections because it doesn't recognize the tech stack — instead, it SHALL investigate and ask the user to confirm findings
- For backend/API projects: focus on endpoints, data flow, integrations, auth mechanisms
- For CLI tools: focus on commands, flags, input/output formats, configuration
- For data pipelines: focus on data sources, transformations, outputs, scheduling
- For hybrid projects: cover all relevant layers

### REQ-DEPLOY: Guide available in consumer projects
- The `writing-specs.md` guide content SHALL be embedded in the skill SKILL.md (not deployed as a separate rule — it's reference material for the skill, not an agent rule)
