<!--
Ordered by dependency, and group 1 is not implementation. Design D3 and D5 leave two carriers
unmeasured — how the context reading arrives, and how "the agent is between turns" is established —
and groups 4 and 5 are shaped differently depending on the answers. Nothing there is built before it
is measured. The measurements already taken are in `measurements.md`; every task below that cites one
names it.

Layer marking, per .claude/rules/code-quality.md: every task says CORE (lib/set_orch/, abstract),
API (lib/set_orch/api/) or WEB (web/). No task puts project-type knowledge into CORE.

This change is written to be UPDATED once `work-cycle-engine-apply-first` finishes: group 3 reads
that engine's verdict, and the shape of a goal whose work was not run as work units is the design's
last open question. Do not resolve it by inventing a second definition of completion.
-->

## 1. Measure first — the two carriers the design left open

- [ ] 1.1 CORE — Establish whether a hook carries the same `context_window` figures the statusline
  payload does, and at what moment it fires. Measured already (`measurements.md` M2): the statusline
  command receives `context_window_size`, `used_percentage`, `remaining_percentage`, `session_id` and
  `transcript_path`. Unknown: whether any hook does. A statusline runs **on render**, which is a proxy
  for "the agent is alive and drawing" — record which of the two is chosen and why. [REQ: remaining-context-is-read-from-the-runtime-per-model-and-an-unknown-reading-never-triggers-a-rotation]
- [ ] 1.2 CORE — Measure how "the agent is between turns" can be established, and prove the chosen
  signal fires in BOTH directions: it must say busy for an agent mid-turn and idle for one waiting.
  Candidates, none assumed: the pty's own rendering, the tail of the transcript, and
  `pendingBackgroundAgentCount` (observed with values 1 and 2). A signal that only ever says idle is
  the failure this task exists to prevent. [REQ: rotation-is-attempted-only-where-the-framework-owns-the-terminal-and-the-agent-is-between-turns]
- [ ] 1.3 CORE — Confirm on a framework-started agent that `--settings <file-or-json>` delivers the
  chosen carrier from a framework-owned path, and that **no file in the project's tree is written**.
  Prove the negative by hashing the tree before and after, not by reading the code. [REQ: remaining-context-is-read-from-the-runtime-per-model-and-an-unknown-reading-never-triggers-a-rotation]
- [ ] 1.4 CORE — Re-run the `/clear` rotation probe against the model and flags the framework actually
  starts agents with, not the probe's Haiku: same pid, same `/proc/<pid>/stat` starttime, one
  transcript before and two after (`measurements.md` M1). A keystroke interface is version-fragile;
  this is the baseline the regression test in 9.3 is written against. [REQ: rotation-happens-in-place-one-process-one-label-one-position-a-new-session]

## 2. The goal record (CORE)

- [ ] 2.1 Define the goal record — text, kind, requester, declaration time, verifiability — and write
  it at the moment the framework starts an agent, keyed by LABEL rather than pid. The label survives
  the rotation in group 5; the pid survives nothing. [REQ: a-framework-started-agent-carries-a-goal-declared-when-it-is-started]
- [ ] 2.2 Refuse a start that supplies no goal, and refuse it without substituting a default, an empty
  goal, or the prompt text. [REQ: a-framework-started-agent-carries-a-goal-declared-when-it-is-started]
- [ ] 2.3 Resolve the goal's kind through `change-lane-profiles` and refuse a kind that vocabulary does
  not define. No second taxonomy is created here — that capability already forbids a lane resolving to
  no behavioural difference. [REQ: a-goal-s-kind-comes-from-the-lane-vocabulary-and-an-unknown-kind-is-refused]
- [ ] 2.4 Report an agent the framework did not start as having **no goal**, distinguishable from a
  goal that is empty and from one that is unknown, and derive nothing from its transcript, cwd, branch
  or declared focus. [REQ: an-agent-the-framework-did-not-start-has-no-goal-and-no-goal-is-invented-for-it]
- [ ] 2.5 Serve the goal from the record while the agent runs, without opening its session log and
  without requiring the agent to be idle or to be asked. [REQ: a-goal-is-readable-while-its-agent-runs-without-reading-the-agent-s-session]

## 3. Closure (CORE)

- [ ] 3.1 Close a goal from the work unit's verdict **diffed against the tree**, reusing
  `work-unit-engine`'s existing check rather than defining completion a second time. The import
  direction is one-way: this reads the engine, the engine never learns about goals. [REQ: a-goal-is-closed-by-checkable-evidence-never-by-the-agent-s-report]
- [ ] 3.2 Leave a goal open when the agent claims completion and the framework's own check disagrees,
  and report the disagreement naming what was claimed and what was found. [REQ: a-goal-is-closed-by-checkable-evidence-never-by-the-agent-s-report]
- [ ] 3.3 Require verifiability to be declared at declaration time; keep an unverifiable goal open
  until a person closes it, present it as awaiting a person rather than as stalled, and refuse to
  reclassify a checkable goal as unverifiable after its check fails. [REQ: a-goal-whose-fulfilment-cannot-be-checked-is-declared-so-when-it-is-made]
- [ ] 3.4 Stop an agent whose goal closed and release its seat; report an agent whose process ended
  with an open goal as exactly that, never as complete, idle or successful. [REQ: a-closed-agent-stops-and-releases-its-seat]
- [ ] 3.5 Keep the goal, its kind, its requester and its closing evidence readable after the agent has
  ended, referencing evidence by identity — a commit, a task marker, a verdict — and copying no line
  of the transcript into the record, a cache or a log. [REQ: the-goal-record-outlives-the-agent-and-carries-no-session-content]

## 4. The context reading (CORE)

- [ ] 4.1 Read remaining context through the carrier chosen in 1.1, taking the window size from what
  the runtime reports for that agent's model. No constant participates in the figure. [REQ: remaining-context-is-read-from-the-runtime-per-model-and-an-unknown-reading-never-triggers-a-rotation]
- [ ] 4.2 Report a reading that cannot be obtained as `unknown`, and make `unknown` inert: no rotation
  is prepared or performed on it. This is the fail direction decided in design D3 — rotating on a
  reading nobody has is destructive, declining merely postpones. [REQ: remaining-context-is-read-from-the-runtime-per-model-and-an-unknown-reading-never-triggers-a-rotation]

## 5. Rotation (CORE)

- [ ] 5.1 Write the handoff before any clear is sent, and verify it **by its trace on disk** —
  present and non-empty — rather than by the report of whatever produced it. [REQ: a-handoff-is-written-before-the-session-is-cleared-and-a-failed-handoff-cancels-the-rotation]
- [ ] 5.2 Cancel the rotation when the handoff was not written or was written empty: no clear is sent
  and the agent continues unchanged, with the failed rotation reported. [REQ: a-handoff-is-written-before-the-session-is-cleared-and-a-failed-handoff-cancels-the-rotation]
- [ ] 5.3 Send the clear through the pseudo-terminal the framework owns, and feed the handoff back
  afterwards. Reuse the existing owner's write path; do not open a second one. [REQ: rotation-happens-in-place-one-process-one-label-one-position-a-new-session]
- [ ] 5.4 Verify the rotation by the **session-identity trace** — a new transcript alongside the old
  under the same process — and report a rotation that cannot be verified as failed rather than
  assumed. A keystroke into a TUI can be swallowed without error (design D5). [REQ: rotation-happens-in-place-one-process-one-label-one-position-a-new-session]
- [ ] 5.5 Keep the label and the surface position across the rotation, and produce no second agent for
  the same work. [REQ: rotation-happens-in-place-one-process-one-label-one-position-a-new-session]
- [ ] 5.6 Leave the goal record unchanged by a rotation, including its declaration time and requester —
  a rotation is not a new agent. [REQ: rotation-happens-in-place-one-process-one-label-one-position-a-new-session]
- [ ] 5.7 Offer no rotation for an agent whose terminal the framework does not hold, and state that as
  the reason rather than presenting a control that goes nowhere. [REQ: rotation-is-attempted-only-where-the-framework-owns-the-terminal-and-the-agent-is-between-turns]
- [ ] 5.8 Gate the clear on the turn-state signal from 1.2: wait while the agent is mid-turn, and send
  nothing at all when turn state cannot be established. Waiting is not abandoning — a due rotation
  stays due. [REQ: rotation-is-attempted-only-where-the-framework-owns-the-terminal-and-the-agent-is-between-turns]
- [ ] 5.9 Record each rotation with its time and the triggering reading, and make the count readable
  beside the goal so an agent thrashing is distinguishable from one that rotated once. [REQ: every-rotation-is-recorded-so-repeated-rotation-is-visible]

## 6. The window-size correction (CORE)

- [ ] 6.1 Remove `CONTEXT_WINDOW_SIZE` from the monitor and take the divisor from the reported size for
  the session's model. Closes register entry **B-10**. [REQ: context-window-size-is-taken-from-what-the-runtime-reports-for-the-model-in-use]
- [ ] 6.2 Report utilization as `unknown` where no size is available, computing nothing from a default
  or from a size seen for another session. [REQ: context-window-size-is-taken-from-what-the-runtime-reports-for-the-model-in-use]

## 7. API

- [ ] 7.1 API — Carry the goal, its kind, its verifiability, its closure state and the rotation count in
  the fleet inventory payload. No existing route changes shape. [REQ: a-goal-is-readable-while-its-agent-runs-without-reading-the-agent-s-session]
- [ ] 7.2 API — Require a goal on the route that starts an agent, and refuse a start without one with a
  message naming what is missing. Coordinate with `fleet-view`'s `agent-fleet-terminal`, whose start
  path supplies none today (design D6). [REQ: a-framework-started-agent-carries-a-goal-declared-when-it-is-started]
- [ ] 7.3 API — Expose closing an unverifiable goal as a deliberate human act, distinct from stopping
  an agent. [REQ: a-goal-whose-fulfilment-cannot-be-checked-is-declared-so-when-it-is-made]

## 8. The screen (WEB)

- [ ] 8.1 WEB — The agent tile carries the goal and its kind, and an agent with no goal says **no goal**
  rather than showing an empty field. An empty field reads as a goal nobody wrote. [REQ: an-agent-the-framework-did-not-start-has-no-goal-and-no-goal-is-invented-for-it]
- [ ] 8.2 WEB — Show a goal awaiting a person as awaiting a person, next to the count of agents already
  waiting that `fleet-view` task 7.2 puts in the sticky header. A goal nobody can close is exactly the
  thing a compacted layout must not hide. [REQ: a-goal-whose-fulfilment-cannot-be-checked-is-declared-so-when-it-is-made]
- [ ] 8.3 WEB — Show the rotation count where it is visible without opening the agent; a repeatedly
  rotating agent looks like a busy one otherwise. [REQ: every-rotation-is-recorded-so-repeated-rotation-is-visible]
- [ ] 8.4 WEB — Render unknown utilization as unknown in the change list — not a zero, not a blank, not
  a percentage. [REQ: context-window-size-is-taken-from-what-the-runtime-reports-for-the-model-in-use]
- [ ] 8.5 WEB — Look at the screen before calling it done, per `.claude/rules/ui-quality.md`. Structural
  counts prove it renders and say nothing about whether the goal line and the state contradict each
  other. [REQ: a-goal-is-readable-while-its-agent-runs-without-reading-the-agent-s-session]

## 9. Proof — written against the result, not the mechanism

- [ ] 9.1 Prove each new test fails without its fix (`git stash` / mutation), and assert the RESTORE as
  well as the mutation — an untracked file cannot be restored by `git checkout`, and the failure is
  reassuring. Clear `__pycache__` between mutations: two mutations of one file can produce identical
  sizes and CPython reuses the earlier `.pyc`. [REQ: a-goal-is-closed-by-checkable-evidence-never-by-the-agent-s-report]
- [ ] 9.2 A test that fails if the goal record is ever populated from an agent's transcript, and one
  that drives the real read paths over a session log carrying a distinctive marker and then looks for
  it on disk and in log records, filenames included — proving first that the marker REACHED the
  reader, otherwise the test passes by reading nothing. [REQ: the-goal-record-outlives-the-agent-and-carries-no-session-content]
- [ ] 9.3 A rotation test driven the way the framework will drive it — through the pty — and asserted on
  the session-identity trace, not on the fact that a clear was written. A test that asserts the write
  passes on a mechanism that no longer clears anything. [REQ: rotation-happens-in-place-one-process-one-label-one-position-a-new-session]
- [ ] 9.4 A test that an unknown context reading and an unestablished turn state each independently
  prevent a clear, and that neither is silently treated as permission. [REQ: remaining-context-is-read-from-the-runtime-per-model-and-an-unknown-reading-never-triggers-a-rotation]
- [ ] 9.5 A test that a completion CLAIM alone does not close a goal — the shape
  `.claude/rules/evidence-discipline.md` records as an agent replying `Done.` with exit 0 over a file
  that did not exist. [REQ: a-goal-is-closed-by-checkable-evidence-never-by-the-agent-s-report]
- [ ] 9.6 A regression check against the baseline set diff, with `PYTHONPATH` pointed at the worktree's
  own source roots and a session-end assertion that no module resolved to another set-core checkout.
  A `cd` into a worktree is a proxy for running its code. [REQ: context-window-size-is-taken-from-what-the-runtime-reports-for-the-model-in-use]

## 10. Debt this change names rather than absorbs

- [ ] 10.1 Record in the bug register whatever group 1 refutes. A measurement that changes the design
  is worth more than the design, and the refuted carrier is the durable half. [REQ: remaining-context-is-read-from-the-runtime-per-model-and-an-unknown-reading-never-triggers-a-rotation]
- [ ] 10.2 Name in `fleet-view`'s task list that its start path must supply a goal (design D6), so the
  coordination is discovered by reading rather than during apply. [REQ: a-framework-started-agent-carries-a-goal-declared-when-it-is-started]

## Acceptance Criteria (from spec scenarios)

### agent-goal-record

**A framework-started agent carries a goal declared when it is started**

- [ ] AC-1: WHEN the framework starts an agent THEN a goal record exists carrying text, kind, requester and declaration time, written before the agent can produce its first turn [REQ: a-framework-started-agent-carries-a-goal-declared-when-it-is-started, scenario: the-goal-is-recorded-before-the-agent-runs]
- [ ] AC-2: WHEN a caller asks the framework to start an agent and supplies no goal THEN the start is refused and no default, empty goal or prompt text is substituted [REQ: a-framework-started-agent-carries-a-goal-declared-when-it-is-started, scenario: a-start-without-a-goal-is-refused]

**An agent the framework did not start has no goal, and no goal is invented for it**

- [ ] AC-3: WHEN an agent is discovered that the framework did not start THEN its goal is reported as absent, distinguishable from empty and from unknown [REQ: an-agent-the-framework-did-not-start-has-no-goal-and-no-goal-is-invented-for-it, scenario: a-hand-opened-session-reports-an-absent-goal]
- [ ] AC-4: WHEN an agent without a goal record is running and its transcript describes work THEN no part of that work is presented as the agent's goal [REQ: an-agent-the-framework-did-not-start-has-no-goal-and-no-goal-is-invented-for-it, scenario: no-goal-is-inferred-from-what-the-agent-is-doing]

**A goal's kind comes from the lane vocabulary and an unknown kind is refused**

- [ ] AC-5: WHEN an agent is started with a kind the lane vocabulary defines THEN the goal record carries that kind [REQ: a-goal-s-kind-comes-from-the-lane-vocabulary-and-an-unknown-kind-is-refused, scenario: a-declared-kind-resolves-through-the-existing-vocabulary]
- [ ] AC-6: WHEN an agent is started with a kind the lane vocabulary does not define THEN the start is refused and the kind is not mapped to a default lane [REQ: a-goal-s-kind-comes-from-the-lane-vocabulary-and-an-unknown-kind-is-refused, scenario: an-unknown-kind-is-refused-rather-than-defaulted]

**A goal is readable while its agent runs, without reading the agent's session**

- [ ] AC-7: WHEN a reader asks for a running agent's goal THEN it is returned from the record without requiring the agent to be idle or to be asked [REQ: a-goal-is-readable-while-its-agent-runs-without-reading-the-agent-s-session, scenario: the-goal-is-readable-during-the-run]
- [ ] AC-8: WHEN a goal is read for an agent whose session log is present THEN the session log is not opened as part of answering [REQ: a-goal-is-readable-while-its-agent-runs-without-reading-the-agent-s-session, scenario: reading-a-goal-does-not-read-the-transcript]

### agent-goal-closure

**A goal is closed by checkable evidence, never by the agent's report**

- [ ] AC-9: WHEN an agent reports its goal complete AND the framework's own check disagrees THEN the goal remains open and the disagreement is reported, naming what was claimed and what was found [REQ: a-goal-is-closed-by-checkable-evidence-never-by-the-agent-s-report, scenario: a-completion-claim-without-matching-evidence-leaves-the-goal-open]
- [ ] AC-10: WHEN a goal names work the engine ran as work units THEN closure comes from the engine's verdict checked against the tree, with no second definition of completion applied [REQ: a-goal-is-closed-by-checkable-evidence-never-by-the-agent-s-report, scenario: closure-reuses-the-work-unit-s-verdict]

**A goal whose fulfilment cannot be checked is declared so when it is made**

- [ ] AC-11: WHEN a goal declared unverifiable has been running and its agent reports it finished THEN the goal stays open and is presented as awaiting a person, not as stalled [REQ: a-goal-whose-fulfilment-cannot-be-checked-is-declared-so-when-it-is-made, scenario: an-unverifiable-goal-is-never-closed-automatically]
- [ ] AC-12: WHEN a goal declared checkable fails its evidence check THEN it is not reclassified as unverifiable [REQ: a-goal-whose-fulfilment-cannot-be-checked-is-declared-so-when-it-is-made, scenario: verifiability-is-not-reassigned-after-the-fact]

**A closed agent stops and releases its seat**

- [ ] AC-13: WHEN a goal closes on verified evidence THEN the agent is stopped and its seat released [REQ: a-closed-agent-stops-and-releases-its-seat, scenario: completion-stops-the-agent]
- [ ] AC-14: WHEN an agent's process ends while its goal is still open THEN it is reported as ended with an open goal, and not as complete, idle or successful [REQ: a-closed-agent-stops-and-releases-its-seat, scenario: a-stop-without-closure-is-not-reported-as-completion]

**The goal record outlives the agent and carries no session content**

- [ ] AC-15: WHEN an agent has ended THEN its goal, kind, requester and closing evidence remain readable [REQ: the-goal-record-outlives-the-agent-and-carries-no-session-content, scenario: the-record-survives-the-agent]
- [ ] AC-16: WHEN a goal is closed THEN what is written references the evidence by identity and copies no line of the agent's transcript into the record, a cache or a log [REQ: the-goal-record-outlives-the-agent-and-carries-no-session-content, scenario: no-conversation-content-is-written-with-the-closure]

### agent-session-rotation

**Remaining context is read from the runtime, per model, and an unknown reading never triggers a rotation**

- [ ] AC-17: WHEN remaining context is read for an agent THEN the size used is the one the runtime reports for that agent's model, with no fixed constant participating [REQ: remaining-context-is-read-from-the-runtime-per-model-and-an-unknown-reading-never-triggers-a-rotation, scenario: the-window-size-comes-from-the-model-in-use]
- [ ] AC-18: WHEN no context reading can be obtained for a running agent THEN it is reported as unknown and no rotation is prepared or performed [REQ: remaining-context-is-read-from-the-runtime-per-model-and-an-unknown-reading-never-triggers-a-rotation, scenario: an-unobtainable-reading-is-unknown-and-inert]

**A handoff is written before the session is cleared, and a failed handoff cancels the rotation**

- [ ] AC-19: WHEN a rotation is performed THEN the handoff file exists and is non-empty before the clear reaches the terminal [REQ: a-handoff-is-written-before-the-session-is-cleared-and-a-failed-handoff-cancels-the-rotation, scenario: the-handoff-exists-before-the-clear-is-sent]
- [ ] AC-20: WHEN the handoff cannot be written, or is written empty THEN no clear is sent and the agent continues unchanged, with the failed rotation reported [REQ: a-handoff-is-written-before-the-session-is-cleared-and-a-failed-handoff-cancels-the-rotation, scenario: a-handoff-that-was-not-written-cancels-the-rotation]

**Rotation happens in place — one process, one label, one position, a new session**

- [ ] AC-21: WHEN an agent's session is rotated THEN the process identity is unchanged, established by more than its process id, and the framework's terminal is not re-created [REQ: rotation-happens-in-place-one-process-one-label-one-position-a-new-session, scenario: the-process-survives-the-rotation]
- [ ] AC-22: WHEN an agent's session is rotated THEN it keeps its label and its place, and no second agent appears for the same work [REQ: rotation-happens-in-place-one-process-one-label-one-position-a-new-session, scenario: the-surface-position-is-not-replaced]
- [ ] AC-23: WHEN an agent whose goal is open is rotated THEN the goal record is unchanged, including its declaration time and requester [REQ: rotation-happens-in-place-one-process-one-label-one-position-a-new-session, scenario: the-goal-is-not-restarted-by-a-rotation]

**Rotation is attempted only where the framework owns the terminal and the agent is between turns**

- [ ] AC-24: WHEN an agent is discovered that the framework did not start THEN no rotation control is offered, and the reason given is that the framework does not hold its terminal [REQ: rotation-is-attempted-only-where-the-framework-owns-the-terminal-and-the-agent-is-between-turns, scenario: a-session-the-framework-did-not-start-is-not-offered-rotation]
- [ ] AC-25: WHEN a rotation is due and the agent is mid-turn THEN the clear is not sent and the rotation waits rather than being abandoned or forced [REQ: rotation-is-attempted-only-where-the-framework-owns-the-terminal-and-the-agent-is-between-turns, scenario: a-busy-agent-is-not-cleared]
- [ ] AC-26: WHEN the framework cannot establish whether the agent is between turns THEN it does not send the clear [REQ: rotation-is-attempted-only-where-the-framework-owns-the-terminal-and-the-agent-is-between-turns, scenario: turn-state-that-cannot-be-established-blocks-the-clear]

**Every rotation is recorded, so repeated rotation is visible**

- [ ] AC-27: WHEN a rotation completes THEN the record carries its time and the context reading that triggered it [REQ: every-rotation-is-recorded-so-repeated-rotation-is-visible, scenario: a-rotation-is-recorded-with-its-trigger]
- [ ] AC-28: WHEN an agent has rotated more than once THEN the count is readable alongside its goal [REQ: every-rotation-is-recorded-so-repeated-rotation-is-visible, scenario: repeated-rotation-is-visible]

### context-window-metrics

**Context window size is taken from what the runtime reports for the model in use**

- [ ] AC-29: WHEN utilization is computed for a change THEN the divisor is the window size the runtime reported for that session's model, with no fixed constant participating [REQ: context-window-size-is-taken-from-what-the-runtime-reports-for-the-model-in-use, scenario: the-size-comes-from-the-model-in-use]
- [ ] AC-30: WHEN no window size is available for a session THEN utilization is reported as unknown and no percentage is computed from a default or from another session's size [REQ: context-window-size-is-taken-from-what-the-runtime-reports-for-the-model-in-use, scenario: an-unreported-size-yields-unknown-not-a-substituted-percentage]
- [ ] AC-31: WHEN the set-web change list renders a change whose utilization is unknown THEN it shows the figure is unavailable, and not a zero, a blank, or a percentage [REQ: context-window-size-is-taken-from-what-the-runtime-reports-for-the-model-in-use, scenario: unknown-utilization-is-displayed-as-unknown]
