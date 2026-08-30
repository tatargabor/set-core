## 1. Resolver (Layer 1: lib/set_orch)

- [x] 1.1 Expose per-candidate tail-window mention counts (`infer_change_weights`), memoized with the existing single bounded read
- [x] 1.2 Archive anchor in the derived path of `resolve_stage`: a candidate deriving to `archive` with ≥ half the leader's weight wins over a non-archived leader
- [x] 1.3 Memo payload holds slugs + counts only; the confidentiality shape test updated to assert exactly that

## 2. Tests

- [x] 2.1 The measured live case: drive-by mention of an active change loses to the session's archived own change
- [x] 2.2 All 51 pre-existing stage tests stay green (recency order, windows, memo TTL, declared path, gaps)

## 3. Ship

- [x] 3.1 `tsc -b` unaffected (Python-only); stage suites 52/52
- [x] 3.2 The running dashboard service restarted OUTSIDE any orchestration run so the payload serves the fixed resolution
- [x] 3.3 Live verification: the archived change resolves `archive` against its session record (direct resolver call on the real transcript + the regression test); the producer has since restarted its session, whose new 26 KB record names no change yet, so the live row honestly shows the `join-failed` gap until it does — stated in the living record, not smoothed over
