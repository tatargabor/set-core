# Tasks: spec-writing-skill

## 1. Skill Implementation

- [x] 1.1 Create `.claude/skills/set/write-spec/SKILL.md` with frontmatter (name, description, trigger pattern) and the full interactive workflow [REQ: REQ-SKILL-INTERACTIVE]
- [x] 1.2 Section 1 — Project Overview & Tech Stack: detect project name from package.json/pyproject.toml/directory name. Detect tech stack from deps and config files. If stack is unfamiliar, spawn Explore agent to investigate key files and architecture. Ask user for project description, target audience, and confirm detected stack [REQ: REQ-SKILL-INTERACTIVE, REQ-RESEARCH]
- [x] 1.3 Section 2 — Data Model / State: if prisma/schema.prisma exists, read and summarize. If SQL/ORM files exist, read those. If no DB, ask what state the app manages (files, API data, config). For CLI tools: what inputs/outputs. For APIs: what resources. Always ask user to confirm and extend detected model [REQ: REQ-SKILL-INTERACTIVE]
- [x] 1.4 Section 3 — Screens / Endpoints / Commands: adapt to project type. Web: ask for page layouts (columns, sections, components). API: ask for endpoint list (method, path, request/response). CLI: ask for commands, flags, output format. For each, ask layout/behavior details. Provide examples from writing-specs.md guide. **Ask interactively if uncertain about any element** [REQ: REQ-SKILL-INTERACTIVE]
- [x] 1.5 Section 4 — Component Behavior / Business Logic: for key interactive elements, ask behavior details. Web: hover, click, error states. API: validation rules, error responses. CLI: edge cases, error handling. If the user says "use defaults" for any part, note it explicitly in spec. **Ask follow-up questions when behavior is ambiguous** [REQ: REQ-SKILL-INTERACTIVE]
- [x] 1.6 Section 5 — Auth & Roles: detect auth deps (NextAuth, passport, JWT libs). Ask user for roles, protected routes/endpoints. If no auth detected, ask if auth is needed. Default: USER + ADMIN if auth deps found [REQ: REQ-SKILL-INTERACTIVE]
- [x] 1.7 Section 6 — Seed / Fixture Data: ask for realistic entity names, credentials (admin + test user), sample content. Warn against placeholder names. For APIs: example request/response payloads. For CLIs: example input files [REQ: REQ-SKILL-INTERACTIVE]
- [x] 1.8 Section 7 — Design Integration: detect .make files, design-system.md, or manual tokens. Web projects: suggest Figma Make + set-design-sync. Non-web: skip or ask if any UI exists. **Ask user explicitly which option they want** [REQ: REQ-SKILL-DESIGN-DETECT]
- [x] 1.9 Section 8 — i18n: detect i18n deps. Ask for locales and default. If no i18n detected, ask if needed. Non-web projects: ask about message localization, config file locale support [REQ: REQ-SKILL-INTERACTIVE]
- [x] 1.10 Section 9 — Testing Strategy: adapt to project type. Web: E2E + unit tests, test user, critical flows. API: integration tests, request/response validation. CLI: input/output tests, error cases. Add test expectations section. **Ask user which flows are most critical to test** [REQ: REQ-SKILL-INTERACTIVE]
- [x] 1.11 Assembly: combine all sections into a single spec.md, add writing-specs.md checklist at the end as comments, write to output path (default docs/spec.md). Show summary of what was generated [REQ: REQ-SKILL-INTERACTIVE]
- [x] 1.12 Post-generation: if .make file was detected and design-system.md doesn't exist yet, offer to run `set-design-sync --input <make-file> --spec-dir docs/`. If design-system.md exists, auto-append ## Design Reference [REQ: REQ-SKILL-DESIGN-DETECT]

## 2. Command Definition

- [x] 2.1 Create `.claude/commands/set/write-spec.md` with usage line, description, and trigger to the skill [REQ: REQ-COMMAND]

## Acceptance Criteria

- [x] AC-1: WHEN `/set:write-spec` is invoked in a Next.js project with Prisma THEN the skill detects the tech stack and pre-populates data model from schema.prisma [REQ: REQ-SKILL-INTERACTIVE]
- [x] AC-2: WHEN a .make file exists in docs/ THEN the skill suggests running set-design-sync and incorporates design tokens [REQ: REQ-SKILL-DESIGN-DETECT]
- [x] AC-3: WHEN the skill completes THEN docs/spec.md exists with all sections filled [REQ: REQ-SKILL-INTERACTIVE]
- [x] AC-4: WHEN `/set:write-spec` is typed in Claude Code THEN the skill is invoked [REQ: REQ-COMMAND]
