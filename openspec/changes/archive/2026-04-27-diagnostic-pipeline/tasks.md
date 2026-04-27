## 1. Core Framework — DiagnosticRule ABC + Context + Result

- [ ] 1.1 Create `lib/set_orch/diagnostic.py` with `DiagnosticContext`, `DiagnosticResult`, and `DiagnosticRule` ABC [REQ: diagnostic-framework, REQ-DIAG-001, REQ-DIAG-002, REQ-DIAG-003]
- [ ] 1.2 Implement `DiagnosticRunner.run_diagnostics()` — iterate rules, first non-None result wins [REQ: REQ-DIAG-004]
- [ ] 1.3 Implement `DiagnosticRunner.apply_result()` — dispatch on action type (fix_config, retry, skip, skip_downstream, escalate) [REQ: REQ-DIAG-004]
- [ ] 1.4 Implement config patching: read config.yaml, merge patches, write back, reload directives [REQ: REQ-CONFIG-004]
- [ ] 1.5 Implement state patching: update change fields from `result.state_patches` [REQ: REQ-DIAG-004]
- [ ] 1.6 Add `DIAGNOSTIC_FIRED` event emission [REQ: REQ-CONFIG-005]

## 2. Profile Interface Extension

- [ ] 2.1 Add `diagnostic_rules() -> list` method to `NullProfile` in `profile_loader.py` (returns `[]`) [REQ: REQ-DIAG-005]
- [ ] 2.2 Update runner to load rules: `built_in_rules + profile.diagnostic_rules()` [REQ: REQ-DIAG-005]

## 3. Built-in Core Rules

- [ ] 3.1 Implement `DependencyCascadeRule` — find transitive dependents, mark `dep_blocked` [REQ: REQ-DIAG-006]
- [ ] 3.2 Add `dep_blocked` status to `Change` dataclass in `state.py` [REQ: REQ-CONFIG-002]
- [ ] 3.3 Update monitor to skip `dep_blocked` changes (no dispatch, no retry) [REQ: REQ-CONFIG-002]
- [ ] 3.4 Implement `dep_blocked` → `pending` recovery when blocked dependency succeeds [REQ: REQ-CONFIG-002]
- [ ] 3.5 Implement `ContextOverflowRule` — detect token overflow, return model upgrade [REQ: REQ-DIAG-007]

## 4. Engine Integration — Failure Path Hooks

- [ ] 4.1 Integrate diagnostics into `gate_runner.py` — call `run_diagnostics()` before marking `failed` on verify exhaustion [REQ: REQ-DIAG-008]
- [ ] 4.2 Integrate diagnostics into `merger.py` — call `run_diagnostics()` before final `merge-blocked` [REQ: REQ-DIAG-008]
- [ ] 4.3 Integrate diagnostics into `engine.py _retry_broken_main_build_safe()` — replace simple retry with diagnostic run [REQ: REQ-DIAG-008]
- [ ] 4.4 Construct `DiagnosticContext` at each integration point with available failure data [REQ: REQ-DIAG-002]

## 5. Config Integration

- [ ] 5.1 Add `diagnostics` section to config schema validation in `config.py` [REQ: REQ-CONFIG-001]
- [ ] 5.2 Parse `diagnostics.*` fields from config.yaml into directives [REQ: REQ-CONFIG-001]
- [ ] 5.3 Gate diagnostic execution on `diagnostics.enabled` and per-failure-type policy [REQ: REQ-CONFIG-003]
- [ ] 5.4 Add `max_diagnostic_retries` tracking per change (separate from verify retries) [REQ: REQ-CONFIG-001]

## 6. Web Diagnostic Rules (set-project-web)

- [ ] 6.1 Create `diagnostics/prisma_client.py` — `PrismaClientRule`: detect "@prisma/client has no exported member" → add post_merge_command [REQ: REQ-WEBDIAG-001]
- [ ] 6.2 Create `diagnostics/missing_deps.py` — `MissingDepsRule`: detect "Module not found: Can't resolve" → run package install [REQ: REQ-WEBDIAG-002]
- [ ] 6.3 Create `diagnostics/merge_gap.py` — `MergeGapRule`: detect "Property does not exist on type" in shared types → retry with context [REQ: REQ-WEBDIAG-003]
- [ ] 6.4 Add `diagnostic_rules()` to WebProfile returning all three rules [REQ: REQ-WEBDIAG-004]
- [ ] 6.5 Create `diagnostics/__init__.py` with rule registry

## 7. Tests

- [ ] 7.1 Unit test: DiagnosticRunner executes rules in order, first match wins
- [ ] 7.2 Unit test: DependencyCascadeRule marks transitive dependents as dep_blocked
- [ ] 7.3 Unit test: ContextOverflowRule detects overflow and returns model upgrade
- [ ] 7.4 Unit test: PrismaClientRule matches Prisma error pattern
- [ ] 7.5 Unit test: MissingDepsRule matches npm module-not-found pattern
- [ ] 7.6 Unit test: Config patching preserves existing config values
- [ ] 7.7 Unit test: dep_blocked → pending recovery when dependency succeeds
- [ ] 7.8 Integration test: engine calls diagnostics before marking change as failed
