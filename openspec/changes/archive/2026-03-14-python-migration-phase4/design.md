## Context

Phases 1-3 delivered the Python orchestration core (`lib/wt_orch/`): logging, subprocess, config, events, state (with mutations, locking, deps, phases, crash recovery), reporter (Jinja2), templates (prompt rendering), and process management. The planner (`lib/orchestration/planner.sh`, 1456 LOC) is the next migration target — it contains 12 functions spanning spec summarization, test infrastructure detection, plan validation, scope overlap analysis, triage gate evaluation, decomposition prompt assembly, agent-based planning, and auto-replan cycles.

About 40% of planner.sh's logic is already delegated to Python via `wt-orch-core` calls (templates.py renders the planning prompt, config.py resolves directives, state.py does topological sort). The remaining bash logic is dominated by JSON manipulation (30+ jq calls), string-based set operations (comm, sort -u for scope overlap), and complex control flow that's fragile in shell.

## Goals / Non-Goals

**Goals:**
- Migrate all data-processing functions from planner.sh to Python with 1:1 function mapping
- Provide `wt-orch-core plan <subcommand>` CLI bridge for each migrated function
- Maintain bash wrappers for functions that orchestrate external tools (run_claude, wt-new, wt-loop, wt-close)
- Full pytest coverage for validation, overlap detection, triage gate, and decomposition context assembly

**Non-Goals:**
- Migrating cmd_plan/cmd_replan/auto_replan_cycle flow control to Python (these call external CLI tools and remain in bash)
- Migrating plan_via_agent (worktree + Ralph dispatch — stays bash)
- Changing plan JSON schema (must remain compatible with existing plans)
- Migrating triage functions defined in digest.sh (generate_triage_md, parse_triage_md, merge_triage_to_ambiguities — those belong to a future digest migration)
- Adding new planner features not in the current bash implementation

## Decisions

### D1: Single planner.py module
**Choice:** Create `lib/wt_orch/planner.py` containing all migrated planner functions.
**Rationale:** The 12 functions form a cohesive concern (plan creation and validation). Estimated ~600-800 LOC — manageable for a single module. Matches the pattern from Phase 2 (state.py) and Phase 3 (reporter.py).
**Alternative:** Split into `planner_validate.py` + `planner_context.py` — rejected because the functions share types and helpers.

### D2: Typed dataclasses for validation results
**Choice:** Define `ValidationResult`, `ScopeOverlap`, `TestInfra` dataclasses for structured return values.
**Rationale:** The bash functions return via exit codes and stdout text — Python can return typed objects that the CLI bridge serializes to JSON. This makes the functions testable and composable.

### D3: Reuse existing modules heavily
**Choice:** Import and reuse config.py (find_input, resolve_directives, brief_hash), state.py (topological_sort), templates.py (render_planning_prompt), events.py (emit).
**Rationale:** These functions were already migrated in Phases 1-3. No point reimplementing or wrapping them — direct Python calls.

### D4: Scope overlap as pure Python set operations
**Choice:** Replace bash comm/sort/tr pipeline with Python `set` intersection/union for Jaccard similarity.
**Rationale:** The bash implementation (lines 253-373) uses comm -12, sort -u, tr, wc -l, and arithmetic — 120 lines of fragile shell. Python equivalent is ~20 lines with `set()` operations. Same algorithm, dramatically simpler.

### D5: Triage gate checks — read-only from digest
**Choice:** planner.py reads ambiguities.json and triage.md for gate checks but does NOT call generate_triage_md or merge_triage_to_ambiguities (those remain in digest.sh).
**Rationale:** Triage generation/parsing is a digest concern. The planner only needs to check the gate status (no_ambiguities/needs_triage/has_untriaged/has_fixes/passed). This avoids pulling digest.sh dependencies into the planner migration.

### D6: CLI bridge subcommands
**Choice:** Add to `wt-orch-core plan` these subcommands: `validate`, `detect-test-infra`, `check-triage`, `check-scope-overlap`, `summarize-spec`, `build-context`, `enrich-metadata`, `replan-context`.
**Rationale:** Each maps 1:1 to a bash function. Bash wrapper becomes a one-liner. Consistent with Phase 1-2 CLI bridge pattern.

### D7: YAML reading via PyYAML (conditional)
**Choice:** Use PyYAML for reading project-knowledge.yaml (cross-cutting files). Import conditionally — if PyYAML not available, skip project-knowledge context (non-fatal).
**Rationale:** PyYAML is already available in the environment (used by yq). Conditional import avoids hard dependency for an optional feature.

## Risks / Trade-offs

**[Risk] Triage gate reads digest files directly** → planner.py must handle missing/malformed files gracefully. Mitigated by defensive JSON parsing with fallback defaults (same as bash behavior).

**[Risk] Template rendering already in templates.py** → planner.py calls templates.py for prompt assembly but adds its own context-gathering (memory, design, project-knowledge). Clear boundary: planner gathers context, templates renders it.

**[Trade-off] Some cmd_plan logic stays in bash** → The run_claude call, heartbeat subprocess, agent dispatch, and wt-loop interaction are inherently shell concerns. Migrating them would require reimplementing subprocess orchestration that bash handles naturally. Future Phase 7 (monitor migration) will address the main loop.

**[Trade-off] Duplicate test infra detection logic** → detect_test_infra has edge cases (lockfile detection, package.json parsing). Python reimplementation must match bash output exactly. Mitigated by comparative tests.
