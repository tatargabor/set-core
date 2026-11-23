## 1. Profile ABC: smoke/scoped command methods

- [x] 1.1 Add three new methods to `ProjectType` in `lib/set_orch/profile_types.py`: `e2e_smoke_command(self, base_cmd: str, test_names: list[str]) -> Optional[str]` (construct command to run only named tests), `e2e_scoped_command(self, base_cmd: str, spec_files: list[str]) -> Optional[str]` (construct command for specific files), `extract_first_test_name(self, spec_path: str) -> Optional[str]` (parse first test name from spec file). All return None by default.
- [x] 1.2 Remove or deprecate `generate_smoke_e2e()` stub (line 297) — replaced by `e2e_smoke_command()`.

## 2. Web module: implement profile methods

- [x] 2.1 In `WebProjectType` (`modules/web/set_project_web/project_type.py`), implement `extract_first_test_name()`: open file, scan lines for `test(['"](.+?)['"]`, return first match. Return None on error.
- [x] 2.2 Implement `e2e_smoke_command()`: join test_names with `|` (each escaped for regex specials), return `{base_cmd} --grep "{pattern}"`. If empty list, return None.
- [x] 2.3 Implement `e2e_scoped_command()`: return `{base_cmd} -- {' '.join(spec_files)}`. If empty list, return None.

## 3. Git-based spec file ownership detection

- [x] 3.1 Create `_detect_own_spec_files(wt_path: str) -> list[str]` in `lib/set_orch/merger.py`. Run `git merge-base HEAD main` then `git diff <base> --name-only --diff-filter=AM`, filter to `*.spec.ts` or `*.spec.js`. Return relative paths. Catch subprocess errors → return empty list.
- [x] 3.2 Add fallback: if git diff returns empty AND `e2e-manifest.json` exists in wt_path, read its `spec_files` array.

## 4. Two-phase E2E gate in merger.py

- [x] 4.1 In `_run_integration_gates()` (`lib/set_orch/merger.py:982`), before the existing e2e block: call `_detect_own_spec_files()`. Glob all `*.spec.ts`/`*.spec.js` in `tests/e2e/` of wt_path. Compute `inherited_specs = all - own`. If own is empty → skip two-phase, use current single-phase behavior as fallback.
- [x] 4.2 Phase 1 (smoke, non-blocking): for each inherited spec, call `profile.extract_first_test_name()` to get smoke test names. Call `profile.e2e_smoke_command(e2e_cmd, smoke_names)` to build command. Run it. If fail: `logger.warning(...)`, record `smoke_e2e_result: "fail"`, `smoke_e2e_output: output[-1000:]`, `smoke_e2e_ms` in state. Do NOT return False.
- [x] 4.3 Phase 2 (own, blocking): call `profile.e2e_scoped_command(e2e_cmd, own_specs)` to build command. Run it. Apply the EXISTING pass/fail/redispatch logic (lines 1001–1052) to this result only.
- [x] 4.4 If profile doesn't support `e2e_smoke_command` (returns None) or `e2e_scoped_command` (returns None): fall back to current single-phase behavior. This ensures non-web project types work unchanged.
- [x] 4.5 Record both phase timings: `gate_e2e_smoke_ms` and `gate_e2e_own_ms`.
- [x] 4.6 If inherited_specs is empty (first change, no prior tests): skip Phase 1, run only Phase 2.

## 5. Scoped redispatch context

- [x] 5.1 In the redispatch block (`merger.py:1018–1035`): only include Phase 2 output in retry_context. If Phase 1 also failed, prepend one-line summary: "Note: {N} inherited smoke tests also failed (non-blocking, not your responsibility)." Include own spec file list: "Your spec files: {files}".

## 6. Test plan: type field

- [x] 6.1 Add `type: str = "functional"` to `TestPlanEntry` (`lib/set_orch/test_coverage.py:504`). Update `to_dict()`/`from_dict()` — default `"functional"` for backward compat.
- [x] 6.2 In `generate_test_plan()` (`lib/set_orch/test_coverage.py:553`): after building entries, group by req_id. First entry with `"happy"` in categories per group → `type = "smoke"`. Rest → `"functional"`.

## 7. Dispatcher: labels + manifest

- [x] 7.1 In `_build_input_content()` (`lib/set_orch/dispatcher.py:1111`): append `**[SMOKE]**` or `**[FUNCTIONAL]**` per entry type. Add instruction: `"Tag SMOKE tests with: test('REQ-X: ...', { tag: '@smoke' }, async ({ page }) => { ... })"`.
- [x] 7.2 In `dispatch_change()`: write `e2e-manifest.json` to worktree root after setup. Content: `{"change": "<name>", "spec_files": ["tests/e2e/<name>.spec.ts"], "requirements": [<req IDs>]}`.

## 8. Coverage tracking

- [x] 8.1 Add `smoke_passed: int = 0`, `smoke_failed: int = 0`, `own_passed: int = 0`, `own_failed: int = 0` to `TestCoverage` (`lib/set_orch/test_coverage.py:144`). Update `to_dict()`/`from_dict()` with 0 defaults.

## 9. E2E methodology update

- [x] 9.1 Update `e2e_test_methodology()` (`modules/web/set_project_web/project_type.py:465`): add SMOKE TAGGING section — first happy-path test per feature uses `{ tag: '@smoke' }`, give syntax example, explain purpose.

## 10. Tests

- [ ] 10.1 Unit: `extract_first_test_name()` — Playwright test() format, describe+test, no match → None. (`tests/unit/test_web_project_type.py` or `modules/web/tests/`)
- [ ] 10.2 Unit: `e2e_smoke_command()` — builds correct --grep pattern, escapes special chars, empty list → None.
- [ ] 10.3 Unit: `e2e_scoped_command()` — builds correct `-- file1 file2` suffix, empty → None.
- [ ] 10.4 Unit: `_detect_own_spec_files()` — mock git subprocess: single file, multi-file, no files, git error → empty. (`tests/unit/test_merger.py`)
- [ ] 10.5 Unit: `generate_test_plan()` type assignment: LOW→smoke, MEDIUM→1 smoke+1 func, HIGH→1 smoke+2 func. Old entry without type → "functional". (`tests/unit/test_test_coverage.py`)
- [ ] 10.6 Unit: `_build_input_content()` emits `[SMOKE]`/`[FUNCTIONAL]` labels. (`tests/unit/test_dispatcher.py`)
- [ ] 10.7 Integration: two-phase gate — mock subprocess: smoke fail+own pass→gate pass, smoke pass+own fail→gate fail with redispatch, both pass→pass, no own files→single phase fallback. (`tests/unit/test_merger.py`)
