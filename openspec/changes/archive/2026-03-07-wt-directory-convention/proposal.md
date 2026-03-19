## Why

Consumer projects currently scatter set-core artifacts across multiple locations: `.claude/orchestration.yaml`, root-level `project-knowledge.yaml`, `docs/orchestration-runs/`, and upcoming requirements/knowledge files have no defined home. This makes it hard for agents, skills, and the orchestrator to discover project-specific wt materials, and there's no clear separation between set-core concerns and the project's own documentation.

A dedicated `wt/` directory convention — analogous to how `openspec/` provides a home for OpenSpec artifacts — gives set-core a structured, discoverable place in every consumer project.

## What Changes

- Define a `wt/` directory convention for consumer projects with standardized subdirectories: `orchestration/`, `knowledge/`, `requirements/`, `plugins/`, `.work/`
- Update `set-project init` to scaffold the `wt/` directory structure
- Update planner, dispatcher, and verifier to look for config/knowledge in `wt/` first, with fallback to legacy locations
- Migrate existing files (orchestration.yaml, project-knowledge.yaml, run logs) into the new structure
- Provide a migration path: `set-project init` detects and offers to move existing files
- Integrate memory system with `wt/`: memory seed files for project bootstrapping (`wt/knowledge/memory-seed.yaml`), memory sync working directory (`wt/.work/memory/`), and exported memory snapshots for team sharing

## Capabilities

### New Capabilities
- `wt-directory-structure`: Defines the `wt/` directory layout, subdirectory purposes, and file conventions for consumer projects
- `set-project-scaffolding`: Extends `set-project init` to create and maintain the `wt/` directory structure, including migration of legacy file locations
- `wt-requirements-registry`: Defines the requirements registry format (`wt/requirements/`) for tracking business requirements with status, priority, source, and links to OpenSpec changes
- `set-memory-integration`: Memory seed files (`wt/knowledge/memory-seed.yaml`) for bootstrapping new installs, memory sync working directory (`wt/.work/memory/`), and the relationship between versioned project knowledge and the runtime memory store

### Modified Capabilities
- `orchestration-config`: Config moves from `.claude/orchestration.yaml` to `wt/orchestration/config.yaml`, with backward-compatible fallback
- `project-init-deploy`: `set-project init` gains `wt/` scaffolding and legacy file migration

## Impact

- **set-project init** (bin/set-project): Add scaffolding logic for `wt/` directory, migration prompts for existing files
- **planner.sh** (lib/orchestration/planner.sh): Update config/knowledge file lookup paths with fallback chain
- **dispatcher.sh** (lib/orchestration/dispatcher.sh): Update project-knowledge lookup path
- **verifier.sh** (lib/orchestration/verifier.sh): Update verification rules lookup path
- **state.sh** (lib/orchestration/state.sh): Update directive loading to check `wt/orchestration/config.yaml` first
- **set-memory** (bin/set-memory): Memory seed import on init, sync uses `wt/.work/memory/` for temp files
- **Consumer projects**: New `wt/` directory created on next `set-project init` run; existing files optionally migrated
