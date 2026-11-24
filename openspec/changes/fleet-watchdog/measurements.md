# fleet-watchdog — live measurements

## 2026-11-24 — first two forced ticks on the development machine (task 2.7)

Run with `SET_WATCHDOG_DIR=<scratch>`, `SETCORE_WATCHDOG_REMEDIATION=propose` (nothing dispatched),
`set-watchdog tick --force`, all five probes. Each finding was checked by hand against its source.

**Tick 1** — 197 s total (set-doctor --json alone ~70 s; one GLM triage call 121.5 s for 6
findings, 5754 chars answered). 6 findings opened:

| probe | finding | checked against | verdict by hand | GLM triage |
|---|---|---|---|---|
| service-health | 4 user units in state `failed` | `systemctl --user list-units --failed`: the same 4 | **true** (all 4) | real ×4 |
| wake-storm | one session, 3 bus wakes | its transcript: the 3 wakes came within 25 min AFTER a typed prompt — a conversation, not an idle session | **false positive** | noise |
| wake-storm | `classifier` (no known marker) | the unmatched records were `isMeta` skill bodies, which are not turn starts | **false positive** | real |

Defects this exposed in the probe, fixed before tick 2 (each now held by a test):
- a non-Stop-hook `isMeta` record (a skill body) was counted as a turn start;
- wake-storm did not require the session to be idle (`last_human_input_seconds` ≥ 60 min now);
- the failed units' owner was left to the model, and it named set-core for two units whose
  `ExecStart` programs live in another registered project's tree. The owner is now resolved from
  the `ExecStart` path, and a hint that names a registered project outranks the model's guess.

**Tick 2** (same store) — 132 s; one GLM call, 67.2 s. The wake-storm false positive **resolved**
(resolve-on-absence measured live). One new `relay-hold` finding (a question held 18 min),
triaged `known:B-214` — correct: that is the open half of B-214. The 4 unit failures stayed open
and were not re-triaged (only new fingerprints are). The `classifier` warning was still open: its
one remaining unmatched record was a `/clear` command row at the top of a cleared session (no
`origin`, `rowSource: local`). Classified as `command` now, and the "no known marker" warning
needs ≥ 3 turn starts.

Cost of a calm tick: zero GLM calls. Cost of these two: 2 calls.
