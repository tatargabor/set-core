## 1. Capture the before, while it still exists

- [x] 1.1 Record the current roster contents to a scratch note — the four `no-session:` keys, which pids they name, and which of those pids have a runtime record. The first write after any change destroys the evidence, and "it got better" needs a before [REQ: an-entry-that-can-never-be-acted-on-lives-only-while-its-agent-is-observed]
- [x] 1.2 Run `tests/unit/test_fleet_roster.py` and record the pass count, so "unedited and still passing" is a comparison rather than an impression. **Measured: 32 passed.** `test_fleet_persistence_boundary.py` was also run and is NOT a valid second baseline here — 2 of its 5 tests were already failing on this platform because its instrument loads `libc.so.6`; that is handled in a separate commit and named in the proposal [REQ: only-a-whole-fleet-write-may-retire-an-entry-this-way]

## 2. The framework's session knowledge reaches the roster

- [x] 2.1 Add the pid-keyed session mapping to `record()`, defaulting to absent so a caller that does not pass it gets exactly today's behaviour [REQ: the-frameworks-session-knowledge-travels-as-a-pid-keyed-mapping-supplied-by-the-caller]
- [x] 2.2 Use it in `_entry_from` ONLY when the runtime's record is silent — the runtime's answer is never overridden [REQ: a-recorded-agents-session-identity-is-taken-from-the-runtime-first-and-the-framework-second]
- [x] 2.3 Preserve the tri-state on the way through: absent (could not ask) stays distinct from empty (asked, holds nothing) [REQ: an-unreachable-source-is-distinct-from-a-source-that-knows-nothing]
- [x] 2.4 Pass it from `api/fleet.py::_record_roster`, taken from the `owned` answer already in hand — no second request to the owner [REQ: the-frameworks-session-knowledge-travels-as-a-pid-keyed-mapping-supplied-by-the-caller]
- [x] 2.5 Hold "the roster opens no socket to the owner" in a test, not in a docstring [REQ: the-frameworks-session-knowledge-travels-as-a-pid-keyed-mapping-supplied-by-the-caller]

## 3. A session-less entry lives only while it is seen

- [x] 3.1 On a whole-fleet write, remove every stored entry with no session identity that the write did not see. Log each removal with its key and the reason, so a vanished entry is never silent [REQ: an-entry-that-can-never-be-acted-on-lives-only-while-its-agent-is-observed]
- [x] 3.2 Gate it on the existing whole-fleet flag; a partial write removes nothing on absence [REQ: only-a-whole-fleet-write-may-retire-an-entry-this-way]
- [x] 3.3 Leave the age bound untouched for entries that carry a session identity, and keep its log line [REQ: the-age-bound-continues-to-govern-every-other-entry]
- [x] 3.4 Test the pair that decides this is safe: an unseen session-less entry goes, an unseen entry WITH a session stays [REQ: an-entry-that-can-never-be-acted-on-lives-only-while-its-agent-is-observed]

## 4. The reason line says what was asked

- [x] 4.1 Reword the no-session reason so it states that no source knows a session, rather than denying that one was ever recorded [REQ: a-reason-line-states-what-was-actually-asked]
- [x] 4.2 **DECIDED: it names both sources.** The line now reads *"no source knows a session for this agent — the runtime has no record of it and the framework did not start it"*. Reason: the previous text was a DENIAL (*"no session id was ever recorded"*), and a reader acting on it has a different next step depending on which source is silent. Naming both tells them nothing is broken and what would change the answer; a short line would have kept the reader guessing which of two places to look [REQ: a-reason-line-states-what-was-actually-asked]
- [x] 4.3 Correct `_no_session_key`'s docstring to describe what it does, and move its two real properties — the pid fallback, and that the key changes when a name appears — into tests [REQ: the-key-builders-documentation-matches-its-behaviour-and-the-behaviour-is-held-in-a-test]

## 5. Prove it, including the part a green suite cannot see

- [x] 5.1 **`test_fleet_roster.py` is byte-identical and passes 32/32** — `git status --porcelain tests/` lists it not at all [REQ: only-a-whole-fleet-write-may-retire-an-entry-this-way]
- [x] 5.2 **Six mutations; four caught, two SURVIVED and both exposed a hollow test rather than a hollow guard.** Caught: the framework's answer overriding the runtime's; the retirement firing on a partial write; the retirement taking a session-carrying row; the API flattening `None` to `{}`. Survived: (a) `sessions=None` vs `{}` — identical BY CONSTRUCTION inside the roster, so the test asserted something that could not fail; (b) clearing `session_id` on every update — the row keyed `S` is only ever rewritten by a sighting that already knows `S`, so the mutation never touched it. The test was rewritten to assert the observable consequence instead, and both wrong patterns are recorded in its docstring. Restore verified by md5 after every mutation. [REQ: a-recorded-agents-session-identity-is-taken-from-the-runtime-first-and-the-framework-second]
- [ ] 5.3 Run the full Python suite and diff the failure SET against a baseline built from HEAD in an isolated worktree with the leak assertion — never against a remembered number, and `--continue-on-collection-errors` or the run stops at the 8 collection errors and compares nothing [REQ: only-a-whole-fleet-write-may-retire-an-entry-this-way]
- [x] 5.4 On this machine, after a real listing round: no `no-session:` entry for a pid that has a runtime record, none for a pid the framework started with a known session, and none for a process that is gone. Compare against the note from 1.1 [REQ: an-entry-that-can-never-be-acted-on-lives-only-while-its-agent-is-observed]
- [x] 5.5 **Looked at, twice, and what was seen is written down.** Fleet screen at the running dashboard, 1600px wide, two screenshots read — one per project.

  A project with only running agents: `All 1 already running` — one statement, no companion line contradicting it.

  The project whose roster was full of junk, after the fix: `All 1 already running` above `⏱ 2 more recorded here, not open`. Two lines that agree, accounting for all three stored rows. Before the change this project held **6** rows, three of them session-less noise, and the panel's offer read `Restore 0 of 1 — 1 cannot be resumed` beside `All 1 restored.`

  What is still there and is NOT this change's: the restored agent's tile is empty (*"the log is readable and holds no conversation"*) — that is the zombie from B-86's race half, explicitly out of scope. And B-87 was not exercised: the contradictory pair needs a stale restore RESULT beside a current offer, and no restore was run in this state. Its absence from the screenshot is not evidence it is fixed. [REQ: a-reason-line-states-what-was-actually-asked]

## Acceptance Criteria (from spec scenarios)

### roster-session-identity

- [x] AC-1: WHEN an agent has both a runtime record and a different framework session THEN the entry carries the runtime's [REQ: a-recorded-agents-session-identity-is-taken-from-the-runtime-first-and-the-framework-second, scenario: the-runtimes-answer-is-used-when-it-exists]
- [x] AC-2: WHEN an agent has no runtime record but the framework started it on a known session THEN the entry carries that session and is not keyed as session-less [REQ: a-recorded-agents-session-identity-is-taken-from-the-runtime-first-and-the-framework-second, scenario: the-frameworks-answer-fills-a-silence]
- [x] AC-3: WHEN neither source knows THEN the entry is recorded with no session id [REQ: a-recorded-agents-session-identity-is-taken-from-the-runtime-first-and-the-framework-second, scenario: neither-source-knows]
- [x] AC-4: WHEN the fleet listing records the roster THEN it passes the session knowledge from the same owner answer it used for labels, with no extra request [REQ: the-frameworks-session-knowledge-travels-as-a-pid-keyed-mapping-supplied-by-the-caller, scenario: the-caller-supplies-it-from-the-answer-it-already-has]
- [x] AC-5: WHEN the roster module is inspected for an owner client THEN none is found [REQ: the-frameworks-session-knowledge-travels-as-a-pid-keyed-mapping-supplied-by-the-caller, scenario: the-roster-opens-no-socket]
- [x] AC-6: WHEN the framework could not be asked THEN an agent with no runtime record is recorded with no session id and nothing is inferred [REQ: an-unreachable-source-is-distinct-from-a-source-that-knows-nothing, scenario: absent-is-not-empty]
- [x] AC-7: WHEN the framework was asked and holds nothing THEN the entry equals one recorded with no mapping at all [REQ: an-unreachable-source-is-distinct-from-a-source-that-knows-nothing, scenario: empty-behaves-as-it-did-before]
- [x] AC-8: WHEN a framework-started agent's entry is read THEN it does not claim no session was ever recorded for it [REQ: a-reason-line-states-what-was-actually-asked, scenario: a-framework-started-agent-no-longer-carries-the-false-reason]
- [x] AC-9: WHEN an entry no source knows a session for is read THEN the reason states that no source knows one [REQ: a-reason-line-states-what-was-actually-asked, scenario: a-genuinely-unknown-agent-says-so-accurately]
- [x] AC-10: WHEN an agent with no name has its no-session key built THEN the key contains its pid [REQ: the-key-builders-documentation-matches-its-behaviour-and-the-behaviour-is-held-in-a-test, scenario: the-pid-fallback-is-asserted]
- [x] AC-11: WHEN the same agent is keyed once without a name and once with one THEN the two keys differ [REQ: the-key-builders-documentation-matches-its-behaviour-and-the-behaviour-is-held-in-a-test, scenario: the-keys-instability-across-a-naming-event-is-asserted]

### roster-entry-lifetime

- [x] AC-12: WHEN a whole-fleet write omits a session-less entry's agent THEN the entry is no longer stored [REQ: an-entry-that-can-never-be-acted-on-lives-only-while-its-agent-is-observed, scenario: an-unseen-session-less-entry-is-removed-by-a-whole-fleet-write]
- [x] AC-13: WHEN a whole-fleet write includes it THEN the entry remains and its first-seen time is unchanged [REQ: an-entry-that-can-never-be-acted-on-lives-only-while-its-agent-is-observed, scenario: a-session-less-entry-that-is-still-seen-is-kept]
- [x] AC-14: WHEN a whole-fleet write omits an entry that carries a session identity THEN that entry remains stored [REQ: an-entry-that-can-never-be-acted-on-lives-only-while-its-agent-is-observed, scenario: an-entry-that-could-be-acted-on-is-never-removed-this-way]
- [x] AC-15: WHEN a write that is not whole-fleet omits a session-less agent THEN the entry remains stored [REQ: only-a-whole-fleet-write-may-retire-an-entry-this-way, scenario: a-partial-write-keeps-what-it-did-not-see]
- [x] AC-16: WHEN a write that is not whole-fleet carries an agent THEN that agent's entry is written [REQ: only-a-whole-fleet-write-may-retire-an-entry-this-way, scenario: a-partial-write-still-records-what-it-did-see]
- [x] AC-17: WHEN a whole-fleet write omits a recently-seen entry that carries a session THEN it remains stored [REQ: the-age-bound-continues-to-govern-every-other-entry, scenario: a-recent-session-carrying-entry-survives-an-absence]
- [x] AC-18: WHEN an entry carrying a session is older than the bound THEN it is removed and the removal is logged with its key and age [REQ: the-age-bound-continues-to-govern-every-other-entry, scenario: an-old-session-carrying-entry-is-still-pruned-by-age]


## Traceability — which test carries which acceptance criterion

| AC | evidence |
|---|---|
| 1–3 | `tests/unit/test_fleet_roster_identity.py` — the source order, the silence being filled, and neither knowing |
| 4 | `test_the_listing_passes_an_unreachable_owner_through_as_unknown` — asserts the caller passes the mapping and does not flatten `None` |
| 5 | `test_the_roster_never_opens_a_socket_to_the_owner` — the module's own rule, held as a check |
| 6–7 | `test_an_unreachable_framework_keeps_the_restorable_row_and_adds_a_throwaway_one`, whose docstring records the two hollow versions this test had before it earned its assertions |
| 8–9 | `test_a_session_less_entry_names_both_sources_rather_than_denying_a_record` |
| 10–11 | the two key-builder tests — the properties that used to live only in a docstring that was false |
| 12–14 | the retirement pair plus the row that carries a session and survives an absence |
| 15–16 | the two partial-write tests |
| 17–18 | `test_the_age_bound_still_governs_a_row_that_carries_a_session`, asserting the log line as well as the removal |

Verified on the machine as well as in tests: the roster went from **8 rows, 4 session-less** to
**4 rows, 0 session-less**, and one project's un-restorable rows from 3 to 1 (the survivor
carries a real session id with no transcript, which the age bound governs and this change
deliberately does not touch).
