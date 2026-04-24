## 1. Core parser and resolver

- [ ] 1.1 Add `modules/web/set_project_web/client_boundary.py` with an import-extraction helper that takes a file path, reads it, and returns `list[ImportEntry]` where `ImportEntry = {line, specifier, imports: list[{name, is_type, is_default, is_namespace}]}` — handles default, named, type-only, namespace, and side-effect-only imports across single- and multi-line syntax [REQ: client-boundary-gate-detects-server-to-client-function-imports]
- [ ] 1.2 Add a `_is_client_module(path)` helper that reads the first ~500 bytes of a file and returns True when the first non-comment, non-whitespace statement is `"use client"` or `'use client'` [REQ: client-boundary-gate-detects-server-to-client-function-imports]
- [ ] 1.3 Add a `TsconfigResolver` class that reads `tsconfig.json` (with JSONC support: strip `//` and `/* */` comments) once per run and exposes `resolve(specifier, importer_path) -> Path | None`, applying `compilerOptions.paths` and `compilerOptions.baseUrl`, then trying `.tsx`, `.ts`, `/index.tsx`, `/index.ts` in order [REQ: client-boundary-gate-resolves-import-paths-using-tsconfig-paths]
- [ ] 1.4 Unit tests `modules/web/tests/test_client_boundary_parser.py`: import-extraction golden tests (default/named/type/namespace/side-effect), and `TsconfigResolver` golden tests (relative, alias, bare, missing file fallback) [REQ: client-boundary-gate-resolves-import-paths-using-tsconfig-paths]

## 2. Gate executor

- [ ] 2.1 Add `execute_client_boundary_gate(ctx)` in `modules/web/set_project_web/gates.py` that walks `src/` and `app/` under `ctx.worktree_path`, runs the parser on each `.ts`/`.tsx`, resolves each import via `TsconfigResolver`, and collects violations [REQ: client-boundary-gate-detects-server-to-client-function-imports]
- [ ] 2.2 In the executor, classify each named import: capitalized → component (allowed), `import type` or `type X` specifier → type (allowed), `*` namespace → violation, `import X` default → allowed (default imports are components by convention), everything else → violation [REQ: client-boundary-gate-detects-server-to-client-function-imports]
- [ ] 2.3 Build the violation report string (files, lines, import statements, FIX hints) and persist structured violations via `ctx.update_change_field("client_boundary_violations", [...])` [REQ: client-boundary-gate-emits-actionable-retry-context-on-failure]
- [ ] 2.4 Set `client_boundary_result` = `"pass"` or `"fail"` and `gate_client_boundary_ms` elapsed time via the gate runner result contract [REQ: client-boundary-gate-emits-actionable-retry-context-on-failure]
- [ ] 2.5 Instrument with `logger.info/debug/warning` following project logging conventions: start/finish INFO with file count + violation count, per-file DEBUG, unresolved-import WARNING [REQ: client-boundary-gate-resolves-import-paths-using-tsconfig-paths]

## 3. Registration and gate pipeline wiring

- [ ] 3.1 In `modules/web/set_project_web/project_type.py::register_gates()`, append a `GateDefinition("client-boundary", execute_client_boundary_gate, position="before:build", defaults={infrastructure: skip, schema: skip, foundational: run, feature: run, cleanup-before: skip, cleanup-after: skip}, result_fields=("client_boundary_result", "gate_client_boundary_ms"))` [REQ: web-profile-registers-the-client-boundary-gate]
- [ ] 3.2 Ensure gate is NOT set to `run_on_integration=True` (deterministic per-commit check; integration is a no-op) [REQ: web-profile-registers-the-client-boundary-gate]
- [ ] 3.3 In `WebProjectType.gate_retry_policy()`, add `"client-boundary": "rerun"` so every retry re-scans the working tree [REQ: web-profile-retry-policy-treats-client-boundary-as-cheap]

## 4. Performance

- [ ] 4.1 Benchmark the executor against a synthetic 2000-file tree; assert runtime ≤ 1000ms on baseline hardware and add the assertion to `test_client_boundary_gate.py::test_perf_2000_files` [REQ: client-boundary-gate-finishes-in-reasonable-time]

## 5. Consumer-facing rule

- [ ] 5.1 Add `templates/core/rules/client-boundary.md` — a concise rule explaining the constraint with one bad example (server→client function call) and one good example (helper in neutral module imported by both sides) [REQ: web-profile-registers-the-client-boundary-gate]
- [ ] 5.2 Ensure the rule is included in the default core rules list deployed by `set-project init` (check `lib/set_orch/profile_loader.py` or the project init script for the rule set reference and add if missing) [REQ: web-profile-registers-the-client-boundary-gate]

## 6. Integration tests

- [ ] 6.1 Add `modules/web/tests/test_client_boundary_gate.py` with fixture projects in `modules/web/tests/fixtures/client_boundary/`: `server_calls_client_fn/` (fail), `server_imports_component/` (pass), `type_only/` (pass), `namespace/` (fail), `client_to_client/` (pass), `alias_import/` (uses `@/` path) [REQ: client-boundary-gate-detects-server-to-client-function-imports]
- [ ] 6.2 End-to-end test: invoke `execute_client_boundary_gate` against each fixture, assert result + violation count + first violation's `file`/`line`/`symbol` fields [REQ: client-boundary-gate-emits-actionable-retry-context-on-failure]

## 7. Documentation and release notes

- [ ] 7.1 Add a brief note to `modules/web/set_project_web/README.md` (create if missing) documenting the new gate and linking to `templates/core/rules/client-boundary.md` [REQ: web-profile-registers-the-client-boundary-gate]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN the client-boundary gate runs against a server file importing `parseX` from a `"use client"` file THEN it SHALL report a VIOLATION with file, line, symbol, and target_module and set `client_boundary_result="fail"` [REQ: client-boundary-gate-detects-server-to-client-function-imports, scenario: server-component-imports-function-from-client-file]
- [ ] AC-2: WHEN a server file imports a capitalized identifier (`Button`) from a `"use client"` file THEN the gate SHALL NOT report a violation [REQ: client-boundary-gate-detects-server-to-client-function-imports, scenario: server-component-imports-component-capitalized-from-client-file-allowed]
- [ ] AC-3: WHEN a server file uses `import type { X }` from a `"use client"` file THEN the gate SHALL NOT report a violation [REQ: client-boundary-gate-detects-server-to-client-function-imports, scenario: type-only-import-from-client-file-allowed]
- [ ] AC-4: WHEN a server file uses `import { type Props, Button } from "./client"` THEN the gate SHALL NOT report a violation for either symbol [REQ: client-boundary-gate-detects-server-to-client-function-imports, scenario: inline-type-import-alongside-component-allowed]
- [ ] AC-5: WHEN a server file uses `import { type Props, parseX } from "./client"` THEN the gate SHALL report a violation for `parseX` only [REQ: client-boundary-gate-detects-server-to-client-function-imports, scenario: inline-type-import-alongside-function-function-flagged]
- [ ] AC-6: WHEN a server file uses `import * as lib from "./client"` THEN the gate SHALL report a violation [REQ: client-boundary-gate-detects-server-to-client-function-imports, scenario: namespace-import-from-client-file-flagged]
- [ ] AC-7: WHEN a server file uses side-effect-only `import "./client"` THEN the gate SHALL NOT report a violation [REQ: client-boundary-gate-detects-server-to-client-function-imports, scenario: side-effect-only-import-allowed]
- [ ] AC-8: WHEN both sides of an import are `"use client"` modules THEN the gate SHALL NOT report a violation [REQ: client-boundary-gate-detects-server-to-client-function-imports, scenario: client-to-client-import-not-checked]
- [ ] AC-9: WHEN the importer uses `./bar` and `bar.tsx` exists next to it THEN the resolver SHALL locate that file [REQ: client-boundary-gate-resolves-import-paths-using-tsconfig-paths, scenario: relative-import-resolved]
- [ ] AC-10: WHEN tsconfig has `"@/*": ["./src/*"]` and import is `@/components/bar` THEN the resolver SHALL locate `src/components/bar.tsx` [REQ: client-boundary-gate-resolves-import-paths-using-tsconfig-paths, scenario: alias-import-resolved-via-tsconfig-paths]
- [ ] AC-11: WHEN the import specifier is a bare module like `next/image` THEN the resolver SHALL skip it [REQ: client-boundary-gate-resolves-import-paths-using-tsconfig-paths, scenario: bare-module-specifier-skipped]
- [ ] AC-12: WHEN an import specifier cannot be resolved THEN the gate SHALL log a WARNING and SHALL NOT fail [REQ: client-boundary-gate-resolves-import-paths-using-tsconfig-paths, scenario: unresolvable-import-logged-and-skipped]
- [ ] AC-13: WHEN the gate fails with one violation THEN the retry_context SHALL contain file, line, import statement, target module, symbol, and a FIX hint [REQ: client-boundary-gate-emits-actionable-retry-context-on-failure, scenario: failure-report-is-actionable]
- [ ] AC-14: WHEN the gate fails with N violations THEN the change state SHALL contain `client_boundary_violations` as a list of N dicts [REQ: client-boundary-gate-emits-actionable-retry-context-on-failure, scenario: structured-violations-persisted]
- [ ] AC-15: WHEN the gate runs on a scaffold with < 2000 source files THEN `gate_client_boundary_ms` SHALL be ≤ 1000 [REQ: client-boundary-gate-finishes-in-reasonable-time, scenario: typical-scaffold]
- [ ] AC-16: WHEN `WebProjectType().register_gates()` is called THEN the returned list SHALL contain the `client-boundary` entry with executor + `position="before:build"` [REQ: web-profile-registers-the-client-boundary-gate, scenario: gate-appears-in-web-profile-registration]
- [ ] AC-17: WHEN gate defaults are resolved for a `feature` change THEN `client-boundary` SHALL be scheduled to run [REQ: web-profile-registers-the-client-boundary-gate, scenario: feature-change-runs-the-gate]
- [ ] AC-18: WHEN gate defaults are resolved for an `infrastructure` change THEN `client-boundary` SHALL be skipped [REQ: web-profile-registers-the-client-boundary-gate, scenario: infrastructure-change-skips-the-gate]
- [ ] AC-19: WHEN a change enters the integration-e2e phase THEN `client-boundary` SHALL NOT execute on the integration branch [REQ: web-profile-registers-the-client-boundary-gate, scenario: gate-does-not-run-on-integration-branch]
- [ ] AC-20: WHEN `client-boundary` retries after a fix THEN the gate SHALL re-scan the working tree with no cached verdict [REQ: web-profile-retry-policy-treats-client-boundary-as-cheap, scenario: retry-re-executes-the-gate]
