## ADDED Requirements

### Requirement: Triage gate evaluation
`check_triage_gate(digest_dir, auto_defer=False)` SHALL evaluate ambiguity triage status and return one of: "no_ambiguities", "needs_triage", "has_untriaged", "has_fixes", "passed".

#### Scenario: No ambiguities file
- **WHEN** `ambiguities.json` does not exist in the digest directory
- **THEN** the result is "no_ambiguities"

#### Scenario: Empty ambiguities
- **WHEN** `ambiguities.json` has zero ambiguities
- **THEN** the result is "no_ambiguities"

#### Scenario: Auto-defer mode
- **WHEN** auto_defer is true and ambiguities exist without triage
- **THEN** all ambiguities are marked "defer" and the result is "passed"

#### Scenario: Triage needed
- **WHEN** ambiguities exist but no triage.md
- **THEN** the result is "needs_triage"

#### Scenario: Untriaged items remain
- **WHEN** triage.md exists but some items have blank decisions
- **THEN** the result is "has_untriaged"

#### Scenario: Items marked fix
- **WHEN** all items are triaged but some marked "fix"
- **THEN** the result is "has_fixes"

#### Scenario: All triaged and passed
- **WHEN** all items triaged with no "fix" decisions
- **THEN** the result is "passed"

### Requirement: Spec summarization
`summarize_spec(spec_path, phase_hint="", model="haiku")` SHALL read a spec file, estimate its token count, and if too large, call Claude to produce a structured summary under 3000 words.

#### Scenario: Small spec returned as-is
- **WHEN** the spec file is under the token threshold
- **THEN** the file content is returned without summarization

#### Scenario: Large spec summarized
- **WHEN** the spec file exceeds the token threshold
- **THEN** a summary prompt is sent to Claude requesting table of contents with completion status and the next actionable phase
- **AND** the summary is returned

#### Scenario: Summarization with phase hint
- **WHEN** a phase_hint is provided
- **THEN** the summary prompt includes "focus on phase: <hint>"

#### Scenario: Summarization failure fallback
- **WHEN** Claude summarization fails
- **THEN** the first 32000 bytes of the spec file are returned as fallback

### Requirement: Decomposition context assembly
`build_decomposition_context(input_mode, input_path, directives, phase_hint="", ...)` SHALL assemble all context needed for the planning prompt and return a structured dict suitable for template rendering.

#### Scenario: Brief mode context
- **WHEN** input_mode is "brief"
- **THEN** the context includes: input_content (raw file), existing_specs, active_changes, test_infra_context, memory_context, project_knowledge_context, design_context

#### Scenario: Digest mode context
- **WHEN** input_mode is "digest"
- **THEN** the context includes: conventions, data_model, execution_hints, domain_summaries, requirements (compact), dependencies, deferred_ambiguities, coverage_info, replan_context

#### Scenario: Memory context integration
- **WHEN** set-memory is available
- **THEN** relevant memories are recalled for planning context (per-roadmap-item in brief mode, phase-based in spec mode)

#### Scenario: Design context integration
- **WHEN** a design snapshot exists
- **THEN** design tokens and component hierarchy are included in the context

#### Scenario: Project knowledge context
- **WHEN** project-knowledge.yaml exists with cross_cutting_files
- **THEN** cross-cutting file paths are included as merge hazard warnings

#### Scenario: Requirements context
- **WHEN** wt/requirements/ directory has captured/planned requirements
- **THEN** those requirements are included for the planner to consider

### Requirement: Plan metadata enrichment
`enrich_plan_metadata(plan_json, hash, input_mode, input_path, replan_cycle=None)` SHALL add metadata fields to a raw plan JSON and return the enriched plan.

#### Scenario: Initial plan metadata
- **WHEN** no existing plan file (first plan)
- **THEN** plan_version is 1, plan_phase is "initial", plan_method is set, created_at is current timestamp

#### Scenario: Replan metadata
- **WHEN** replan_cycle is provided
- **THEN** plan_phase is "iteration", and depends_on references to completed changes are stripped

#### Scenario: Input hash tracking
- **WHEN** input_path points to a file
- **THEN** input_hash (SHA-256) is computed and stored in metadata

### Requirement: Replan context collection
`collect_replan_context(state_path)` SHALL gather completed change info, file lists, memory context, and E2E failure data for the next replan cycle.

#### Scenario: Completed changes context
- **WHEN** state has changes with status "done", "merged", or "merge-blocked"
- **THEN** their names and roadmap items are collected

#### Scenario: File change context
- **WHEN** merged changes exist
- **THEN** git log is queried for files modified by those changes (up to 20 per change)

#### Scenario: E2E failure context
- **WHEN** state has phase_e2e_failure_context
- **THEN** the failure context is included for the next planning cycle
