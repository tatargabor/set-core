## 1. Digest module — core infrastructure

- [ ] 1.1 Create `lib/orchestration/digest.sh` with module skeleton: `cmd_digest()` entry point, `source` from `wt-orchestrate`, error handling for missing/empty paths
- [ ] 1.2 Implement `scan_spec_directory()` — recursively find all `.md` files, detect master file (matching `v*-*.md` or `README.md` at root), compute combined SHA256 source hash, error on empty directory
- [ ] 1.3 Implement `build_digest_prompt()` — concatenate all spec files with file path headers, add structured output instructions for: (1) file classification (convention/feature/data/execution), (2) conventions.json extraction, (3) data-definitions.md generation, (4) requirements.json with REQ-* IDs and `cross_cutting` field, (5) domains/*.md, (6) dependencies.json with implicit dependency detection, (7) ambiguities.json with underspecified/contradictory/missing_reference detection, (8) verification checklist de-duplication, (9) embedded behavioral rule extraction from data files. Include granularity heuristic ("one requirement = one independently testable behavior"), classification heuristic, de-dup instruction ("each unique behavior = exactly one REQ-* ID"), and embedded rule instruction ("data files may contain business logic — extract as REQ-* IDs")
- [ ] 1.4 Implement `call_digest_api()` — single Claude API call via `run_claude`, extract JSON and MD sections from response
- [ ] 1.5 Implement `write_digest_output()` — write to `wt/orchestration/digest/`: index.json (with `spec_base_dir`, source_hash, file list, file classifications, `execution_hints`, timestamp), conventions.json (project-wide rules), data-definitions.md (entity/catalog summaries), requirements.json (behavioral requirements only, de-duplicated), dependencies.json, ambiguities.json (detected spec issues), coverage.json (empty skeleton `{"coverage": {}, "uncovered": []}`), domains/*.md. Atomic: write to temp dir first, move on success, no partial writes on failure
- [ ] 1.6 Implement `validate_digest()` — check all source files classified (convention/feature/data/execution), requirement IDs unique and match `REQ-{DOMAIN}-{NNN}` format, no duplicate requirements (same behavior from different source files), domain summaries exist for each domain in requirements, dependencies reference valid requirement IDs, conventions.json is valid JSON, ambiguities.json is valid JSON, cross-cutting requirements have `affects_domains` field
- [ ] 1.7 Implement `stabilize_ids()` — on re-digest, load existing requirements.json, match by `source` + `source_section`, reuse matched IDs, assign new IDs for unmatched, mark removed requirements with `"status": "removed"`
- [ ] 1.8 Add `--dry-run` flag to `cmd_digest()` — print digest output to stdout without writing files

## 2. Digest CLI integration

- [ ] 2.1 Add `digest` subcommand to `bin/wt-orchestrate` — route to `cmd_digest()`, accept `--spec <path>` and `--dry-run` flags, add `--help` text
- [ ] 2.2 Add `coverage` subcommand to `bin/wt-orchestrate` — read `wt/orchestration/digest/coverage.json` and `requirements.json`, display per-domain breakdown (total/planned/dispatched/running/merged/uncovered), handle no-digest and digest-but-no-plan states, show orphaned entries from removed requirements

## 3. Planner — directory input and digest awareness

- [ ] 3.1 Modify `find_input()` in `lib/orchestration/utils.sh` — add directory branch: when `SPEC_OVERRIDE` is a directory (`[[ -d ]]`), set `INPUT_MODE="digest"` and `INPUT_PATH` to absolute directory path
- [ ] 3.2 Add `check_digest_freshness()` in `digest.sh` — compare `index.json` `source_hash` against current spec directory hash (using `scan_spec_directory()` hash function), return stale/fresh status
- [ ] 3.3 Add auto-digest trigger in `cmd_plan()` in `planner.sh` — if `INPUT_MODE="digest"` and no fresh digest exists, call `cmd_digest()` before proceeding, log "Auto-generating digest..."
- [ ] 3.4 Add digest-aware prompt section in planner prompt template in `planner.sh` — when `INPUT_MODE="digest"`, inject: (1) conventions.json as "Project Conventions" section, (2) data-definitions.md as "Data Model Reference", (3) execution_hints from index.json as optional guidance, (4) domains/*.md, (5) requirements.json, (6) dependencies.json. Conventions and data appear BEFORE requirements so planner sees project-wide rules first
- [ ] 3.5 Extend planner output schema — add `spec_files[]`, `requirements[]`, and `also_affects_reqs[]` per change in the planner prompt instructions and in `validate_plan()` JSON schema validation (check arrays exist, requirements reference valid IDs, also_affects_reqs reference cross-cutting IDs with a primary owner)
- [ ] 3.6 Implement `populate_coverage()` in `digest.sh` — after plan generation, iterate requirements.json IDs, map each to the change that lists it in `requirements[]`, write coverage.json with status `planned` and `also_affects` from `also_affects_reqs[]` fields
- [ ] 3.7 Implement `check_coverage_gaps()` in `digest.sh` — find non-removed requirement IDs not covered by any change, populate `uncovered` array, print warning if non-empty

## 4. Planner — replan coverage context

- [ ] 4.1 Extend replan prompt section in `planner.sh` — when replanning with existing coverage, inject "Already covered (merged)" and "Already covered (running)" requirement lists so planner skips them
- [ ] 4.2 Fix `auto_replan_cycle()` in `planner.sh` — add `"digest"` to the input_mode restore logic (currently only handles `"spec"` and `"brief"`)

## 5. Dispatcher — spec context in worktrees

- [ ] 5.1 Modify `dispatch_change()` in `lib/orchestration/dispatcher.sh` — read `spec_base_dir` from `wt/orchestration/digest/index.json`, read `spec_files[]` from state for the change, copy listed files preserving directory structure to `$wt_path/.claude/spec-context/`. Also copy `conventions.json` and `data-definitions.md` from digest dir to every worktree (regardless of spec_files). Log warning for missing files, skip if no `spec_files` field (backward compat)
- [ ] 5.2 Extend proposal.md pre-creation in `dispatcher.sh` — add "Source Specifications" section listing `.claude/spec-context/` file paths, "Requirements" section listing owned requirement IDs with titles and briefs, and "Cross-Cutting Requirements" section listing `also_affects_reqs` IDs with a note to incorporate (not re-implement)
- [ ] 5.3 Add `.claude/spec-context/` to worktree `.gitignore` during dispatch (append if not present)

## 6. Coverage status updates

- [ ] 6.1 Add `update_coverage_status()` function in `digest.sh` — given a change name and new status, use `jq` to update all matching requirements in coverage.json
- [ ] 6.2 Hook `update_coverage_status()` into orchestrator state transitions at these sites: `dispatch_change()` in `dispatcher.sh` (→ dispatched), monitor loop in `monitor.sh` (→ running when commits detected), merge handler in `merger.sh` or equivalent (→ merged)

## 7. Decompose skill update

- [ ] 7.1 Update `.claude/skills/wt/decompose/SKILL.md` — add multi-file spec reading strategy: if `SPEC_PATH` is a directory, read master file first, then use Agent tool to analyze domains in parallel, output digest-compatible format

## 8. Backward compatibility and integration

- [ ] 8.1 Verify single-file spec flow — run `wt-orchestrate plan --spec <single-file>` end-to-end and confirm no behavioral changes (no digest triggered, no new fields required in plan output, dispatch works as before)
- [ ] 8.2 End-to-end integration test — run full digest → plan → dispatch cycle on the `tests/e2e/scaffold-complex/` fixture, verify: digest produces valid index.json/requirements.json/domains/*.md, plan includes spec_files + requirements per change, coverage.json has no uncovered requirements, dispatch copies spec files to worktree
