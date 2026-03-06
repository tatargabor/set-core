# Project Knowledge

Structured project knowledge system enabling AI agents to understand feature relationships, cross-cutting concerns, and verification expectations. Two layers: a machine-readable registry for orchestration tooling, and a lightweight rule for per-turn agent guidance.

## Requirements

### R1: Project Knowledge File
- Located at `.claude/project-knowledge.yaml` in consumer projects
- YAML format with `version: 1` header
- Three sections: `cross_cutting_files`, `features`, `verification_rules`
- NOT loaded into agent context per-turn — only read by orchestration tooling (planner, dispatcher, verifier)

### R2: Cross-Cutting Files Section
- Maps logical names to file paths and descriptions
- Example entries: sidebar component, i18n locale files, activity logger, shared type definitions
- Used by the planner for merge avoidance: if two parallel changes both touch a listed file, they should be sequentialized

### R3: Features Section
- Maps feature names to file path globs, cross-cutting file references, and related features
- Optional `reference_impl: true` flag marks a feature as the canonical pattern to follow
- `touches` array references cross-cutting file names from R2
- Used by the dispatcher for targeted context injection

### R4: Verification Rules Section
- Array of rules with `name`, `trigger`, `expect`, `severity`
- Triggers: `file_modified`, `file_created`, `pattern_added` (regex match in diff)
- Expectations: `file_modified` (another file should also be in the diff)
- Severity: `error` (blocks merge) or `warning` (logged, non-blocking)
- Evaluated by the verifier against `git diff` after implementation

### R5: Cross-Cutting Checklist Rule
- Template `.claude/rules/cross-cutting-checklist.md` with path-scoped frontmatter
- Contains a concise checklist of cross-cutting concerns (5-8 items)
- Path-scoped to dashboard/feature file patterns so agents see it during implementation
- Project-specific content — wt-tools provides a template, projects customize it

### R6: Scaffolding Tool
- `wt-project init-knowledge` subcommand
- Scans project for common patterns: dashboard pages, i18n files, sidebar component, activity logger
- Generates a draft `.claude/project-knowledge.yaml` with detected features and cross-cutting files
- One-time scaffolding tool, not ongoing sync
- User reviews and commits the generated file

### R7: Planner Integration (Merge Avoidance)
- Planner reads `cross_cutting_files` section during plan generation
- Injects merge hazard analysis into the decompose prompt: "These files are frequently edited by multiple changes. When two changes both need them, dispatch sequentially."
- `check_scope_overlap()` enhanced to check file-path overlap using the registry

### R8: Dispatcher Integration (Context Assembly)
- When dispatching a change, reads the relevant feature's `touches` list
- Injects targeted cross-cutting context into the change's proposal (not the whole registry)
- Includes reference implementation path if available

### R9: Verifier Integration (Post-Implementation Checks)
- After tests and build pass, evaluates `verification_rules` against the git diff
- Produces warnings or errors that are included in the verify gate result
- Errors block merge; warnings are logged and reported but non-blocking

### R10: Graceful Degradation
- If `project-knowledge.yaml` does not exist, all integration points are no-ops
- Missing features in the registry just mean less merge avoidance for those features
- The system works without project-knowledge — it is an enhancement, not a requirement
