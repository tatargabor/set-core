---
paths:
  - "openspec/**"
---

# OpenSpec Artifacts — Scope and Content Rules

## Single OpenSpec for the Monorepo

OpenSpec lives at `set-core/openspec/` — the single source of truth. Built-in modules (`modules/web/`, `modules/example/`) do NOT have their own `openspec/` directories. A change that modifies both core and module code uses ONE change in the root openspec.

External plugins (separate repos) maintain their own `openspec/` with their own specs.

## No Project-Specific Content

This is an open-source project. OpenSpec change artifacts (proposal, design, tasks, specs) must NOT contain project-specific references — no client/project names, no absolute paths like `/home/user/code/project`, no specific metrics tied to a single deployment. Use generic descriptions instead (e.g., "projects with non-ASCII content" instead of naming a specific project). If investigation was done on a specific project, generalize the findings before writing artifacts.

## Cross-Layer Changes Are Normal

A single change often touches both `lib/set_orch/` (core) and `modules/web/` (module). This is expected when:
- Adding a new method to `ProjectType` ABC + implementing it in a module
- Fixing a core gate + updating module-specific patterns
- Refactoring the profile interface

The task list should clearly mark which files are core vs module.
