# Tasks: merge-conflict-prevention

## Group 1: Generated File Coverage (GF-1, GF-2)

- [x] T1: Add `coverage/**` and `node_modules/**` to wt-merge GENERATED_FILE_PATTERNS
  > Already done in linter pass — verified present in bin/wt-merge

- [x] T2: Verify pattern consistency across all three pattern lists
  > Added .set-core/, .next/, dist/, build/, coverage/, node_modules/ to dispatcher.py _AUTO_RESOLVE_PREFIXES
  > Added next-env.d.ts to _CORE_GENERATED_FILE_PATTERNS

## Group 2: Engine Serialization (ES-1 through ES-5)

- [x] T3: Add `_drain_merge_then_dispatch()` helper to engine.py
  > New function: retry_merge_queue() → _dispatch_ready_safe()

- [x] T4: Replace main loop dispatch+merge with serialized pattern
  > engine.py: check merge_queue, drain then dispatch, or dispatch only

- [x] T5: Update token-budget path to use drain helper
  > engine.py ~L382: _drain_merge_then_dispatch replaces _retry_merge_queue_safe

- [x] T6: Update checkpoint path to use drain helper
  > engine.py ~L347: _drain_merge_then_dispatch replaces _retry_merge_queue_safe

- [x] T7: Update self-watchdog path to use drain helper
  > engine.py ~L1054: _drain_merge_then_dispatch replaces _retry_merge_queue_safe

## Group 3: Validation

- [x] T8: Verify wt-merge partial_mode=true is committed and correct
  > Confirmed: partial_mode="true" unconditionally at L789

- [x] T9: Verify scaffold .gitattributes is committed and correct
  > Confirmed: merge=ours entries in both run.sh and run-complex.sh
