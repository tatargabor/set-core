# Tasks — smart-truncation

## Phase 1: Core utility (DONE)

- [x] Create `lib/set_orch/truncate.py` with `smart_truncate()`, `smart_truncate_structured()`, `truncate_with_budget()`
- [x] Create `tests/unit/test_truncate.py` with edge case coverage (19 tests)
- [x] Run unit tests — 19/19 pass

## Phase 2: Apply to verifier

- [ ] `verifier.py:447` — `build_output[-3000:]` in `_build_unified_retry_context` → `smart_truncate_structured`
- [ ] `verifier.py:455` — `test_output[-3000:]` in retry context → `smart_truncate_structured`
- [ ] `verifier.py:464` — `review_output[-3000:]` in retry context → `smart_truncate_structured`
- [ ] `verifier.py:877` — `output[-max_chars:]` in `run_tests_in_worktree` → `smart_truncate`
- [ ] `verifier.py:788-791,831-834` — security rules `[:1500]` + `total > 4000 break` → `truncate_with_budget`
- [ ] `verifier.py:2109` — `build_output[-2000:]` gate failure → `smart_truncate_structured`
- [ ] `verifier.py:2530` — `verify_output[-2000:]` spec verify retry → `smart_truncate_structured`

## Phase 3: Apply to templates

- [ ] `templates.py:280` — `output_tail[-2000:]` smoke fix → `smart_truncate_structured`
- [ ] `templates.py:305` — `build_output[-3000:]` build fix → `smart_truncate_structured`

## Phase 4: Apply to merger

- [ ] `merger.py:1253` — smoke output `[-1000:]` → `smart_truncate_structured`
- [ ] `merger.py:1090` — build output `[-2000:]` → `smart_truncate_structured`
- [ ] `merger.py:1118` — test output `[-2000:]` → `smart_truncate_structured`
- [ ] `merger.py:1315` — e2e output `[-8000:]` → `smart_truncate_structured`
- [ ] `merger.py:1333` — e2e stdout/stderr for retry → `smart_truncate_structured`

## Phase 5: Apply to engine + dispatcher + builder

- [ ] `engine.py:1278` — `build_output[-2000:]` rebuild prompt → `smart_truncate_structured`
- [ ] `engine.py:1471` — `e2e_output[-2000:]` replan context → `smart_truncate_structured`
- [ ] `dispatcher.py:137-138` — rule injection `total > 4000 break` → `truncate_with_budget` + omitted note
- [ ] `dispatcher.py:922` — `build_output[:2000]` dispatch context → `smart_truncate_structured`
- [ ] `builder.py:146` — `error_output[-3000:]` build fix → `smart_truncate_structured`
- [ ] `gate_runner.py:291` — `result.output[-2000:]` gate output → `smart_truncate`

## Phase 6: Verify

- [ ] Run full unit test suite
- [ ] Verify no import errors or syntax issues across all modified files
