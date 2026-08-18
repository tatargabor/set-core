<!--
Ordered by dependency, and the first group is not implementation. Group 1 settles the unknowns that
design §6 puts on the terminal's critical path; groups 5, 8 and 9 are sized differently depending on
their answers, so nothing there is built before it is measured.

Updated 2026-08-17: 1.1 and 1.2 are DONE and their answer is negative — a running session cannot be
adopted by resuming it (design §6.1). The shrink that answer entitled group 8 to was declined by the
user, so the group keeps its planned size and 1.5 carries the search for another route. Four
requirements were added in that round — a refusal to resume a live session, an agent that registers
nothing, waiting-for-a-person as a state, and the orphaned waiters the design had measured but no
task had covered (the user placed them here rather than in a change of their own) — with their tasks
and acceptance criteria below.

Updated 2026-08-18 for the work-cycle engine change, which lands before this one: it OWNS the data
this screen was going to guess at. Five places moved — the goal and progress an agent reports, the
capability report, starting a unit, answering an open decision, and a project stopped on a question
with no agent running. Everything the engine supplies degrades to the same behaviour this change
already defines for a missing bus: absent, stated, never inferred.

Layer marking, per .claude/rules/code-quality.md: every task says CORE (lib/set_orch/, abstract),
API (lib/set_orch/api/) or WEB (web/). No task puts project-type knowledge into CORE.
-->

## 1. Measure first — what decides the terminal's reach

- [x] 1.1 CORE — Measure whether a running agent session can be adopted into a framework-owned pseudo-terminal by resuming it: start a session by hand, resume it into an owned pty, and check that its history is intact and that input reaches it. Record the exact command and its output. **DONE 2026-08-17 — the answer is no.** Resuming a live session returns exit 0, the intact history and the same session id, appends to the same log, and forks the conversation into a second branch the running original never sees. Nothing reports it. [REQ: adoption-of-a-running-session-is-measured-before-it-is-relied-upon]
- [x] 1.2 Write the answer into `design.md` §6 — including a negative one, with what was run and what it returned. A negative result shrinks group 8 and is a finding, not a failure. **DONE 2026-08-17 — written up as design §6.1**, with the commands, the observation table and the log's branch structure. ⚠ The group-8 shrink it anticipated was **declined by the user**: the terminal stays at its planned size and adoption is pursued by another route (design §5.2), so no task below was cut on the strength of this. [REQ: adoption-of-a-running-session-is-measured-before-it-is-relied-upon]
- [ ] 1.3 CORE — Encode the measured default, which 1.1 turned from provisional into settled: every session the framework did not start reports no terminal. [REQ: adoption-of-a-running-session-is-measured-before-it-is-relied-upon]
- [x] 1.4 Re-measure the three counts the design rests on (live sessions, sessions with a registry seat, sessions with a live waiter) and note them with today's date. They were taken on one machine on one day; a task list built on a stale count inherits it silently. Resolve every process match to an identity — a bare `pgrep` count includes the counting command itself, which is how the waiter figure was first wrong. **DONE 2026-08-18 — all three moved, and one grew a shape nobody planned for.** 21 live sessions (was 12); 11 with a registry seat (52 %, was 9 of 12); 6 with a live waiter of their own (was 4 of 12); 17 orphaned waiters (was ~30). A naive command-line match returned 31 false positives, all shell snapshots — the identity rule held. **One session owns four waiters at once**, so a missing-waiter check must count rather than test presence. Written up as design §6.3. [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire]
- [x] 1.5 CORE — Measure the remaining adoption route before anything depends on it: whether the runtime's own cross-session channel, or a remote-control mode, can reach a session that is **already running**. Both are known to be enabled where a session starts; neither is known to attach to one afterwards. A negative here is a finding, not a failure. **DONE 2026-08-18 — the channel reaches a running session but does not attach to one.** Input is delivered, an idle peer wakes, a reply returns as a message; there is no output stream, no pty, no way to observe the peer's screen. Remote Control is **not measured** — the account has used it but nothing is connected here, so no remote row was listed; not measured is not negative. Design §6.3. [REQ: adoption-of-a-running-session-is-measured-before-it-is-relied-upon]
- [x] 1.6 Re-measure the delivery outcomes against the runtime's own channel, not only the framework's bus — the fourth outcome (held for the recipient's human, and expiring on its own) was found there and exists in no other source. **DONE 2026-08-18 — the fourth outcome reproduced, and the measurement corrected design §3 in the dangerous direction.** The runtime channel sees 21 of 21 live sessions against the framework bus's 11, verifies the sender's **pid** from the socket while marking the name a claim, and returns a real refusal for an unresolvable recipient instead of a constant. **But a delivered send and a held send return the identical `success: true`** — so the send call reports *acceptance for delivery*, not delivery, and no tile may render its answer as an outcome. The true outcome arrives **asynchronously ~4–5 min later** as a runtime notice keyed by the recipient's verified socket, not by the returned `msg_id`. **Expiry measured too, as a SECOND notice** ~6 min after the send — so one instruction has three states, accepted → held → expired, and the middle one is not terminal; a surface that renders the first notice and stops shows *held* for a dead message. Design §6.3. [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire]

## 2. Discovery — the inventory (CORE)

- [x] 2.1 New module `lib/set_orch/fleet/discovery.py`: enumerate live agent processes and read each one's working directory. Do not match project paths inside command lines. **DONE 2026-08-18** — `lib/set_orch/fleet/discovery.py`. Identity from `/proc/<pid>/comm`, project from `cwd`; a naive command-line match was re-measured at **31 false positives** the same day and a test holds that wrong pattern. Finding CB-8 folded in: a `-p` subprocess is classified `oneshot` and excluded by default rather than tiled. [REQ: an-agent-is-discovered-from-process-state-not-from-a-command-line]
- [x] 2.2 Resolve a working directory to a project through the repository's common git directory, so every worktree of one repository resolves to one project; report the branch per agent. **DONE 2026-08-18** — resolved through `git rev-parse --git-common-dir`, so every worktree of one repository reports one project; branch reported per agent. Verified live: two sessions in one worktree collapsed to one project, 22 agents across 12 projects. [REQ: a-working-directory-resolves-to-a-project-through-git-not-by-path-matching]
- [x] 2.3 Bind a process to its session log from the messaging registry's recorded binding; mark any heuristic fallback as unconfirmed, and prefer no binding to an arbitrary one. **DONE 2026-08-18, from a BETTER source than the task named.** The binding comes from the runtime's own per-session record (`~/.claude/sessions/<pid>.json`), not from the messaging registry: measured that day, **23 records to 23 live processes, one to one, nothing stale**, against the framework registry's 11 of 21. So the 4-of-9 heuristic is not merely labelled, it is unnecessary — there is no guessing path at all, and `binding_confirmed` is False only when no record exists. [REQ: a-process-is-bound-to-its-session-log-by-recorded-fact-and-a-guess-says-so]
- [~] 2.4 Build the project list as the union of project registry, messaging registry and live process working directories, and report per entry which sources knew about it. **PARTIAL 2026-08-18 — two of the three sources.** The union covers the project registry and live process working directories, and names them per entry (`sources`). The **messaging registry is not yet a source**, so a project known only to it is still missing. Deliberately left open rather than marked done: the union's whole value is that it is complete. [REQ: the-inventory-is-a-union-of-its-sources-and-names-them]
- [ ] 2.5 Walk process ancestry to the first agent ancestor; report the parent by seat identity, never by pid, and derive directing/executing from the relation. [REQ: an-agent-started-by-another-agent-is-identified-as-its-descendant]
- [ ] 2.6 Report per project which framework capabilities are connected, derived from files present; keep the capability set data, and distinguish not-connected from unknown. [REQ: a-project-reports-what-it-has-wired-in-and-dim-is-not-absent]
- [ ] 2.7 Assert the non-persistence boundary in code: no session-derived content reaches disk, cache or log, and diagnostics name file and failure kind only. [REQ: nothing-derived-from-an-agent-s-session-is-persisted]
- [ ] 2.8 CORE — List a live agent that has no registry entry and no session log at all, from process discovery alone, naming the sources that lacked it. Two measured causes: a session started as another session's child (its transcript is off and it never registers), and a session still at its start-up trust prompt. Both are alive, both are invisible to the native source. [REQ: an-agent-that-registers-nothing-is-still-an-agent]
- [ ] 2.9 CORE — ⚠ **Measured 2026-08-18 (design §6.4): the record exists for 1 project of 12, and covers 4 of that project's 16 rule files — so `inferred` is the NORMAL case here, not the footnote this task implies, and `un-ledgered` must not render as `stale`: for those files the framework cannot separate a project's own edit from its own drift, and *cannot tell* is the honest report.** Take the capability report from the project's module install record where one exists — modules and their versions — and report a version the project expects but does not have as a mismatch. Fall back to inferring from files only where no record exists, and mark such an entry as inferred. A declaration and a guess answer different questions. [REQ: a-project-reports-what-it-has-wired-in-and-dim-is-not-absent]

## 3. State — read from the log (CORE)

- [x] 3.1 `lib/set_orch/fleet/state.py`: derive last movement from the session log's mtime, never from a registry heartbeat. **DONE 2026-08-18** — `lib/set_orch/fleet/state.py`, from the session log's mtime. A test asserts the module's source contains no reference to the record's `status` field, because that field was measured at a **median age of 11 hours, maximum 83** across 23 live sessions. [REQ: activity-is-read-from-the-session-log-never-from-a-heartbeat]
- [x] 3.2 Define working as an outstanding tool call — a `tool_use` in the tail with no matching `tool_result` — and name the tool and its elapsed time. **DONE 2026-08-18** — an outstanding `tool_use` with no matching `tool_result`, naming the tool and its elapsed time. **Verified by self-experiment, not by assertion:** sampling this session's own log while a `Bash` call was open showed the state flip to `working` with that tool named. ⚠ The runtime flushes a turn in batches — the log was ~25s stale mid-turn — so `quiet` means *no outstanding call as of the last flush*, and the surface says so. [REQ: an-outstanding-tool-call-is-what-working-means]
- [x] 3.3 Return unknown, never idle, for anything undetermined; distinguish an absent key from an empty value (a missing `status` raises where `.get()` returns a false negative). **DONE 2026-08-18** — three distinct ways of knowing nothing (no log bound, log absent, log unparsable) each return `unknown` **with a reason**, and a mutation replacing `unknown` with `idle` fails three tests. [REQ: a-state-that-cannot-be-determined-is-unknown-never-idle]
- [ ] 3.4 Report a phase only where the agent declared one; emit nothing where undeclared, and keep role separate from phase. [REQ: a-phase-is-reported-only-where-the-agent-declared-one]
- [ ] 3.5 Carry a declared blockage independently of the measured state, so blocked-while-busy is representable. [REQ: a-declared-blockage-is-independent-of-the-measured-state]
- [x] 3.6 Keep the list path to `stat` + tail only; full parse happens when a log is opened. **DONE 2026-08-18** — `stat` plus a bounded 256 KB tail; a test builds a 60 000-line log and asserts the tail path does not read it whole. Measured live: 22 agents in **0.21 s**. [REQ: listing-every-agent-does-not-read-every-log-in-full]
- [ ] 3.7 Bound the number of file watchers so it does not grow with the agent count — and before believing any watcher measurement, allocate one by hand and check it succeeds: an exhausted watcher table makes every allocation fail and reports a reassuring zero. [REQ: watching-the-fleet-costs-a-bounded-number-of-file-watchers]
- [ ] 3.8 CORE — Report *waiting for a person* as a state of its own, carrying what it waits for, taken from the runtime's session record rather than the log — the log cannot distinguish an agent stopped at a prompt from one that finished its turn. Check the record's freshness before believing it (its timestamps have been measured days stale) and yield unknown when it is stale. [REQ: waiting-for-a-person-is-a-state-of-its-own-and-it-says-what-for]
- [ ] 3.9 CORE — Read an agent's declared purpose and its progress from the work-cycle engine's recorded run state (which change, which group, the last verdict); measure progress in completed tasks, never in turns or events; report a record whose process is gone as stale; report no purpose at all where there is no record. [REQ: what-an-agent-is-working-towards-is-read-from-the-engine-s-record-never-guessed]

## 4. Instruction — over the bus (CORE)

- [ ] 4.1 `lib/set_orch/fleet/instruct.py`: deliver an instruction addressed to a specific session; refuse rather than broadcast when identity cannot be resolved. [REQ: an-instruction-is-delivered-over-the-messaging-bus]
- [ ] 4.2 Take the delivery outcome from the channel's own answer, and map it to the four outcomes — including *held pending the recipient's human*; report unknown rather than upgrading it to delivered. [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire]
- [ ] 4.3 Use any direct local channel only to prompt a mailbox check, never to carry content, and degrade to the durable path alone when it is unavailable. [REQ: a-direct-channel-may-ring-the-bell-but-never-carry-the-message]
- [ ] 4.4 Report an agent with no bus identity as observable but not instructable, with the reason; keep discovery and state working when no bus exists at all. [REQ: an-agent-that-cannot-be-instructed-says-so-where-the-input-would-be]
- [ ] 4.5 Carry the lapse of a held message through to the caller: a hold expires on its own, so the outcome shown must be corrected rather than left standing. An outcome with a clock is not a resting state. [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire]
- [ ] 4.6 CORE — Find waiter processes whose session has exited, resolving each candidate to a process identity and confirming it against its session; never derive a candidate from a match count. Treat an undeterminable session as alive. [REQ: an-orphaned-waiter-is-shown-and-removing-it-is-an-offer-rather-than-a-tidy-up]
- [ ] 4.7 CORE — Deliver an answer to an open decision into the deferred-work connector, keyed by change and task, and report it as **recorded** rather than received. The asking session is usually gone by then, so a message addressed to it would be delivered to nobody. [REQ: an-answer-to-an-open-decision-goes-to-the-connector-not-to-a-session]

## 5. Terminal — the owned process (CORE)

- [ ] 5.1 `lib/set_orch/fleet/terminal.py`: start an agent under a pseudo-terminal the framework owns, and record which population each agent belongs to (started here / adopted / foreign) as a carried fact. [REQ: a-terminal-exists-only-for-a-process-the-framework-started-or-adopted]
- [ ] 5.2 Refuse any write into a terminal the framework does not own, and never report a terminal as available for a foreign session. [REQ: a-terminal-exists-only-for-a-process-the-framework-started-or-adopted]
- [ ] 5.3 Relay terminal output and browser keystrokes in both directions, persisting nothing; diagnostics name the stream and failure kind only. [REQ: terminal-traffic-travels-in-both-directions-and-is-never-persisted]
- [ ] 5.4 Define the lifetime: the agent survives a browser disconnect and is reattachable; stopping is an explicit action, never a consequence of closing a view. [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting]
- [ ] 5.5 Implement the measured answer for a service restart: the terminal does **not** survive it, because its handle dies with the owning process — a pty master cannot be reacquired from outside (design §6.1). The agent keeps running and stays reachable over the bus; only the terminal column becomes no, and it is never listed as attachable. [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting]
- [ ] 5.6 Log the process lifecycle with pid and exit signal, per code-quality rules, so an orphan is findable from the logs rather than only from the screen. [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting]
- [ ] 5.7 CORE — Refuse to resume any session with a live process bound to it, and expose no control that would; treat an undeterminable liveness as live. A resume that succeeds here forks the running agent's conversation silently. [REQ: resuming-a-session-that-is-running-is-refused-not-offered]
- [ ] 5.8 CORE — Split the agent-owning process from the web service: a second unit owns agent lifecycle, the dashboard serves UI and API, and the two communicate. Extends the existing per-project supervisor daemon's shape rather than inventing one. Design §6.2. **The owner must stay THIN, and this is a requirement rather than a style note (user, 2026-08-18):** its uptime IS the terminal's uptime, because a pty master cannot be reacquired, so every restart of it is a terminal outage. It holds ptys, relays bytes, and starts/stops named scopes — nothing else. Discovery, state, the API and the screen stay in the web service, which stays freely restartable. A line of business logic added here is a future outage. [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting]
- [ ] 5.9 CORE — Start every surface-started agent in its own transient scope, so it survives a restart of **either** service — the split alone does not deliver this, it only moves which service kills it. Measured: a transient scope lands as a sibling of the service, not a child. Assert the cgroup placement, not just that the process started. [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting]
- [ ] 5.10 CORE — Start a work unit by invoking the engine's command entry point under the framework-owned pty, never by spawning an agent directly; keep starting a bare interactive session a separate, separately-labelled act. A run started outside the engine is absent from the engine's state, which is the source this screen reads. [REQ: starting-work-goes-through-the-engine-s-one-entry-point-not-a-second-spawn-path]
- [ ] 5.11 CORE — Recover an agent whose owner died: **stop the orphaned transient scope by name, then resume the session into a fresh pty** — replacement, not reattachment, because the terminal handle died with the owner. The order is load-bearing and must be enforced in code rather than left to the operator: resuming while the old scope is still up reproduces the §6.1 fork (two live sessions appending to one transcript, neither aware of the other, nothing reporting it). The surface refuses to offer resume until the scope is down, and says which of the two acts it is performing. Verified 2026-08-18 that a transient scope lands at `app.slice/<name>.scope`, a sibling of the web service, and stops by name. [REQ: adoption-of-a-running-session-is-measured-before-it-is-relied-upon]

## 6. API (API)

- [~] 6.1 New route module in `lib/set_orch/api/` serving the fleet inventory: projects, agents, sources, branch, parent seat, role, capability flags. No existing route modified. **PARTIAL 2026-08-18 — the inventory is served; parent seat is NOT.** `lib/set_orch/api/fleet.py` serves `GET /api/fleet/agents` with projects, agents, sources and branch. Parent seat waits on task 2.5, which is not in this slice. Finding CB-16 is closed here: the router is registered FIRST in `api/__init__.py`, ahead of the `/api/{project}/...` wildcards that would otherwise answer it as a project named "fleet". [REQ: the-inventory-is-a-union-of-its-sources-and-names-them]
- [ ] 6.2 Per-agent state and log-tail endpoints, and a full-parse endpoint used only when a log is opened. [REQ: listing-every-agent-does-not-read-every-log-in-full]
- [ ] 6.3 Send endpoint returning the three-way delivery outcome verbatim from the bus. [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire]
- [ ] 6.4 Bidirectional terminal stream endpoint, plus start and stop for a surface-started agent. [REQ: terminal-traffic-travels-in-both-directions-and-is-never-persisted]
- [ ] 6.5 Endpoint installing a module into a project **through the module installer**, returning its report verbatim — skipped files with reasons, a changed-nothing outcome, a refusal naming a missing required module. No capability-specific install path, and no ownership check invented here: provenance is the installer's job. [REQ: an-install-offered-from-the-screen-goes-through-the-module-installer-and-shows-what-it-did-not-do]
- [ ] 6.6 Endpoints listing orphaned waiters and removing one **by named process**; the removal takes the same discipline as the install — it writes into a tree the framework does not own — and refuses anything it cannot confirm dead. No bulk-remove endpoint — a cleanup that takes a list is one mistaken list away from killing live waiters. [REQ: an-orphaned-waiter-is-shown-and-removing-it-is-an-offer-rather-than-a-tidy-up]

## 7. The screen (WEB)

- [ ] 7.1 `web/src/pages/Fleet.tsx`: two panels — projects left, the selected project's agents right, selection without a further navigation step. [REQ: projects-on-the-left-the-selected-project-s-agents-on-the-right]
- [ ] 7.2 Project tile carrying agent count and enough state to see a waiting agent without selecting the project, and keeping that count readable when compacted. [REQ: a-project-tile-carries-the-state-of-the-agents-inside-it]
- [ ] 7.3 Agent tile: identity, state, log excerpt, input; state and input survive every density; an unconfirmed binding is marked as a guess. [REQ: an-agent-tile-carries-state-log-excerpt-and-its-own-input]
- [ ] 7.4 Enlarge one tile with the others remaining as single-line rows carrying state and activity; a row selects back. [REQ: a-tile-can-be-enlarged-and-the-other-agents-stay-visible-as-rows]
- [ ] 7.5 Per-project view state: enlarged tile, density, unsent draft; a remembered view never determines state, and a remembered choice outranks the single-agent default. [REQ: view-state-is-remembered-per-project]
- [ ] 7.6 Dictation into the same input, reusing the existing voice component; absent rather than failing when unconfigured. [REQ: dictation-writes-into-the-same-input-as-typing]
- [ ] 7.7 Show the delivery outcome on the tile it was sent from, distinguishing the three, and offer the remedy where nothing will wake the agent. [REQ: the-delivery-outcome-is-shown-where-the-message-was-sent]
- [ ] 7.8 Lineage on the tile: an edge plus a reference to the parent seat, and the measured role. [REQ: an-agent-started-by-another-agent-is-identified-as-its-descendant]
- [ ] 7.9 Capability icons per project, dim for not-connected and distinct from unknown, rendered from data rather than a fixed list. [REQ: a-project-reports-what-it-has-wired-in-and-dim-is-not-absent]
- [ ] 7.10 `web/src/App.tsx`: the root route renders the fleet; the projects overview keeps its own route and a navigation entry. [REQ: the-fleet-is-the-landing-screen-and-an-unfinished-answer-is-not-an-empty-one]
- [ ] 7.11 The pre-answer state: while discovery has not returned, the screen says it is looking — never an empty fleet, a zero, or the word idle. Distinguish it from a completed discovery that genuinely found nothing. [REQ: the-fleet-is-the-landing-screen-and-an-unfinished-answer-is-not-an-empty-one]
- [ ] 7.12 Open-the-log view shows the raw conversation (design §5.8); leave room for the existing timeline as a later tab without building it. [REQ: listing-every-agent-does-not-read-every-log-in-full]
- [ ] 7.13 Show orphaned waiters where the missing-waiter remedy is offered, each removable individually and never in one sweep; state that removal kills a process. The debris belongs next to the offer that would otherwise add to it. [REQ: an-orphaned-waiter-is-shown-and-removing-it-is-an-offer-rather-than-a-tidy-up]
- [ ] 7.14 WEB — Surface a project that holds work awaiting a human answer even when it has no running agent, counting what is awaiting rather than who is present. This is the ordinary shape of stopped work, and an agent-centric tile renders it as nothing to do. [REQ: a-project-awaiting-a-human-is-surfaced-even-when-no-agent-is-running]
- [ ] 7.15 WEB — Render the install affordance where the capability report says *not connected*, and render the installer's report where the reader is standing: skipped files with reasons, changed-nothing said out loud, a missing requirement as a refusal rather than a warning. A screen that renders only success re-creates the silence the installer's contract forbids. [REQ: an-install-offered-from-the-screen-goes-through-the-module-installer-and-shows-what-it-did-not-do]

## 8. Terminal in the browser (WEB)

- [ ] 8.1 Add the terminal emulator component as a frontend dependency and render it against the stream endpoint. **Sized by 1.1, now answered: surface-started sessions only** — resume-based adoption is refuted, and the user chose not to shrink the rest of this group on the strength of it. [REQ: terminal-traffic-travels-in-both-directions-and-is-never-persisted]
- [ ] 8.2 Offer a terminal only where one can exist; where it cannot, state the reason in its place and keep the bus input. No control that opens onto nothing. [REQ: a-tile-offers-a-terminal-only-where-one-can-exist-and-says-why-when-it-cannot]
- [ ] 8.3 Start-an-agent action, and reattach to a running one after a reload. [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting]

## 9. Proof — written against the result, not the mechanism

- [ ] 9.1 Discovery against known truth: assert the result against the registry's own recorded process-to-session bindings, failing on any *silent* mismatch. A labelled guess is not a failure; an unlabelled one is. [REQ: a-process-is-bound-to-its-session-log-by-recorded-fact-and-a-guess-says-so]
- [ ] 9.2 Delivery, driven apart: a fixture that produces each of the four outcomes explicitly — including *held*, and a held message that then lapses — asserting the reported outcome each time. A test asserting only that the send call was made passes identically on all of them. [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire]
- [ ] 9.3 Assert the union and the worktree rule on a fixture with two worktrees of one repository and a project known only to a process — the two cases that produced the false absence and the phantom projects. [REQ: a-working-directory-resolves-to-a-project-through-git-not-by-path-matching]
- [ ] 9.4 Assert unknown-not-idle on all three of its causes: no log yet, unreadable log, absent (not empty) status key. [REQ: a-state-that-cannot-be-determined-is-unknown-never-idle]
- [ ] 9.5 `web/tests/e2e/`: drive the terminal the way a person does — a keystroke entering the browser terminal component reaches the agent and its output returns there. Writing to the pty file descriptor from the test is not accepted as proof. [REQ: the-terminal-is-proven-by-driving-it-as-a-person-drives-it]
- [ ] 9.6 `web/tests/e2e/`: assert the negative half too — no terminal offered for an agent the framework did not start. A positive-only check passes on a build that offers one for every agent. [REQ: the-terminal-is-proven-by-driving-it-as-a-person-drives-it]
- [ ] 9.7 `web/tests/e2e/`: the landing screen's pre-answer state — with discovery delayed, assert the screen says it is looking and shows no zero. [REQ: the-fleet-is-the-landing-screen-and-an-unfinished-answer-is-not-an-empty-one]
- [ ] 9.8 Stash-check every test written above: `git stash && pytest <new tests>; git stash pop`. A test that passes without its fix proves nothing and looks like proof forever. Restore by a means that works on untracked files, and re-grep the file to confirm the restore landed. [REQ: a-state-that-cannot-be-determined-is-unknown-never-idle]
- [ ] 9.9 Regression check against a real baseline: `git worktree add --detach`, `PYTHONPATH` at the baseline's own three source roots, plus the session-end leak assertion from `CLAUDE.md`. Compare failure sets, not counts. [REQ: nothing-derived-from-an-agent-s-session-is-persisted]
- [ ] 9.10 Open the screen and look at it, with several agents in several projects and at least one waiting. Structural counts prove it renders; they say nothing about whether it is readable or whether two fields contradict each other. [REQ: an-agent-tile-carries-state-log-excerpt-and-its-own-input]

- [ ] 9.11 Assert the resume refusal on a session with a live process, and assert the *shape* of the damage it prevents rather than only the refusal: a fixture that performs the forbidden resume must produce a log with two leaves under one parent. A test asserting only "the button is disabled" passes on a build whose backend still resumes. [REQ: resuming-a-session-that-is-running-is-refused-not-offered]
- [ ] 9.12 Assert that an agent with no registry entry and no session log is listed anyway, driven from a process that genuinely has neither — not from a record with the fields blanked, which is a different case and the one that already works. [REQ: an-agent-that-registers-nothing-is-still-an-agent]
- [ ] 9.13 Assert *waiting for a person* against a stale record as well as a fresh one: fresh yields waiting with its reason, stale yields unknown. A positive-only test passes on a build that believes any record it finds. [REQ: waiting-for-a-person-is-a-state-of-its-own-and-it-says-what-for]

- [ ] 9.14 Assert the orphan-waiter rule in its dangerous direction: a fixture holding one dead-session waiter, one live one, and one whose session cannot be determined — only the first may be offered or removed. Include a candidate whose match arises from the checking command itself, and assert it is not offered. A test that only proves the orphan gets removed passes on a build that removes all three. [REQ: an-orphaned-waiter-is-shown-and-removing-it-is-an-offer-rather-than-a-tidy-up]
- [ ] 9.15 Assert the no-agent case directly: a fixture with an open decision recorded against a task and **no process running**, asserting the project is surfaced as awaiting an answer. A test that only covers a waiting agent passes on a build blind to the common case. [REQ: a-project-awaiting-a-human-is-surfaced-even-when-no-agent-is-running]
- [ ] 9.16 Enumerate the surface's start paths and assert exactly one starts a work unit. A test that only checks the engine's command works passes on a build that also kept a direct spawn. [REQ: starting-work-goes-through-the-engine-s-one-entry-point-not-a-second-spawn-path]
- [ ] 9.17 Assert the install surface on its unhappy paths, which are the ones a demo never reaches: an install that skips every file, one that writes nothing, and one refused for a missing required module. Assert what the SCREEN shows in each, not what the installer returned — the two differ exactly when the surface is wrong. [REQ: an-install-offered-from-the-screen-goes-through-the-module-installer-and-shows-what-it-did-not-do]

## 10. Debt this change names rather than absorbs

- [ ] 10.1 Record that `openspec/specs/unified-navigation/spec.md` is stale against the shipped app — it describes `/manager/*` and `/set/*` sidebar routes that are now legacy redirects in `App.tsx`. Not fixed here; a retroactive correction of its own, so the landing change does not quietly inherit a rewrite of an unrelated spec. [REQ: the-fleet-is-the-landing-screen-and-an-unfinished-answer-is-not-an-empty-one]

- [ ] 10.2 Record the user's request of 2026-08-18 for a **third source of state — an interpreting agent** that reads the other sessions' output and, knowing which task each was given, reports what is running, waiting or finished. **Deferred by the user until the base functions work**, and deliberately NOT built here. Design §6.5 settles the shape it must take before anyone starts: an interpretation is a guess and is labelled one, it may add a state but never replace a measured one nor silence an `unknown`, its uncertainty resolves toward *needs a look* rather than *done*, its "finished" is a claim shown next to a checkable trace or next to the absence of one, and it persists nothing derived from what it reads. It belongs in its own capability rather than in `agent-fleet-state`, which is defined as measurement. [REQ: a-state-that-cannot-be-determined-is-unknown-never-idle]

## Acceptance Criteria (from spec scenarios)

### agent-fleet-inventory

**An agent is discovered from process state, not from a command line**

- [ ] AC-1: WHEN an agent process runs with a working directory inside a known project and a command line that names no path THEN it appears in the inventory, attributed to that project [REQ: an-agent-is-discovered-from-process-state-not-from-a-command-line, scenario: an-interactive-session-is-discovered]
- [ ] AC-2: WHEN an agent process runs in a directory belonging to no registered project THEN it appears in the inventory, and its project is reported as known from the process alone [REQ: an-agent-is-discovered-from-process-state-not-from-a-command-line, scenario: a-session-in-an-unregistered-directory-is-still-discovered]

**A process is bound to its session log by recorded fact, and a guess says so**

- [ ] AC-3: WHEN the registry records a session id and owning process id for a live process THEN the inventory binds that process to that session log, marked as confirmed [REQ: a-process-is-bound-to-its-session-log-by-recorded-fact-and-a-guess-says-so, scenario: a-recorded-binding-is-used]
- [ ] AC-4: WHEN no registry record exists and a session log is inferred for a process THEN the binding is reported as unconfirmed, and the surface shows it as a guess [REQ: a-process-is-bound-to-its-session-log-by-recorded-fact-and-a-guess-says-so, scenario: a-heuristic-binding-is-marked]
- [ ] AC-5: WHEN several session logs are equally plausible for one process and no record exists THEN the agent is listed with no session log rather than with an arbitrary one [REQ: a-process-is-bound-to-its-session-log-by-recorded-fact-and-a-guess-says-so, scenario: no-binding-is-better-than-a-wrong-one]

**The inventory is a union of its sources, and names them**

- [ ] AC-6: WHEN an agent runs in a project that appears in neither registry THEN the project is listed, sourced from process discovery [REQ: the-inventory-is-a-union-of-its-sources-and-names-them, scenario: a-project-known-only-to-a-live-process-is-listed]
- [ ] AC-7: WHEN a registered project has no live agent THEN it is listed as holding no agents, and is not dropped from the list [REQ: the-inventory-is-a-union-of-its-sources-and-names-them, scenario: a-registered-project-with-no-agent-is-listed]
- [ ] AC-8: WHEN a project is known to more than one source THEN the entry names each source that knew about it [REQ: the-inventory-is-a-union-of-its-sources-and-names-them, scenario: sources-are-reported-rather-than-merged-away]

**An agent that registers nothing is still an agent**

- [ ] AC-9: WHEN an agent process runs having inherited a marker that suppresses its registration and its transcript THEN it is listed from process discovery, with its project, and its missing sources named [REQ: an-agent-that-registers-nothing-is-still-an-agent, scenario: a-child-session-appears]
- [ ] AC-10: WHEN an agent process is alive but has not yet registered because it is waiting at a start-up prompt THEN it is listed, and reported as waiting rather than as unknown-and-idle [REQ: an-agent-that-registers-nothing-is-still-an-agent, scenario: a-session-at-a-start-up-prompt-appears]
- [ ] AC-11: WHEN an agent has no registry entry and no session log THEN the entry states which sources lacked it, rather than presenting a gap as a determined state [REQ: an-agent-that-registers-nothing-is-still-an-agent, scenario: a-record-s-absence-is-reported-not-resolved]

**A working directory resolves to a project through git, not by path matching**

- [ ] AC-12: WHEN two agents run in two worktrees of the same repository THEN both are attributed to that one project, each reporting its own branch [REQ: a-working-directory-resolves-to-a-project-through-git-not-by-path-matching, scenario: agents-in-different-worktrees-belong-to-one-project]
- [ ] AC-13: WHEN a worktree directory sits beside the main checkout with a similar name THEN no separate project entry is created for it [REQ: a-working-directory-resolves-to-a-project-through-git-not-by-path-matching, scenario: a-worktree-is-not-a-project-of-its-own]
- [ ] AC-14: WHEN an agent runs in a directory under no repository THEN the directory itself is the project, and no branch is reported [REQ: a-working-directory-resolves-to-a-project-through-git-not-by-path-matching, scenario: a-directory-that-is-not-a-git-repository]

**An agent started by another agent is identified as its descendant**

- [ ] AC-15: WHEN an agent process descends from another agent process THEN the inventory reports the parent's seat identity [REQ: an-agent-started-by-another-agent-is-identified-as-its-descendant, scenario: a-spawned-agent-names-its-parent]
- [ ] AC-16: WHEN an agent process has no agent ancestor THEN it is reported as having no parent, which is the ordinary case [REQ: an-agent-started-by-another-agent-is-identified-as-its-descendant, scenario: an-agent-started-by-a-person-has-no-parent]
- [ ] AC-17: WHEN an agent has at least one agent descendant THEN it is reported as directing, and each descendant as executing [REQ: an-agent-started-by-another-agent-is-identified-as-its-descendant, scenario: role-follows-from-the-relation-not-from-a-guess]

**A project reports what it has wired in, and dim is not absent**

- [ ] AC-18: WHEN the files that constitute a capability are present in a project THEN the project reports that capability as connected [REQ: a-project-reports-what-it-has-wired-in-and-dim-is-not-absent, scenario: a-connected-capability]
- [ ] AC-19: WHEN those files are absent but the capability applies to any project THEN the project reports it as not connected, not as absent [REQ: a-project-reports-what-it-has-wired-in-and-dim-is-not-absent, scenario: a-capability-that-could-be-connected]
- [ ] AC-20: WHEN a project carries a record of the modules it installed THEN the capability report is taken from that record rather than from the presence of files [REQ: a-project-reports-what-it-has-wired-in-and-dim-is-not-absent, scenario: a-declared-install-record-is-the-source]
- [ ] AC-21: WHEN a project expects a module version it does not have THEN the mismatch is reported, distinctly from the module being absent [REQ: a-project-reports-what-it-has-wired-in-and-dim-is-not-absent, scenario: a-version-mismatch-is-reported-as-such]
- [ ] AC-22: WHEN no install record exists and presence is inferred from files THEN the report marks that entry as inferred rather than declared [REQ: a-project-reports-what-it-has-wired-in-and-dim-is-not-absent, scenario: an-inference-says-it-is-one]
- [ ] AC-23: WHEN a new capability is added to the framework THEN it can be reported without changing the surface's rendering logic [REQ: a-project-reports-what-it-has-wired-in-and-dim-is-not-absent, scenario: the-capability-set-is-data-not-a-fixed-list]

**Nothing derived from an agent's session is persisted**

- [ ] AC-24: WHEN the inventory reads the tail of a session log to derive state THEN the excerpt is served to the caller and retained nowhere [REQ: nothing-derived-from-an-agent-s-session-is-persisted, scenario: a-log-excerpt-is-read-and-dropped]
- [ ] AC-25: WHEN reading a session log fails or its content cannot be parsed THEN the diagnostic names the file and the failure kind, and quotes no line of it [REQ: nothing-derived-from-an-agent-s-session-is-persisted, scenario: a-failure-reports-shape-not-content]


### agent-fleet-state

**Activity is read from the session log, never from a heartbeat**

- [ ] AC-26: WHEN an agent's session log was written to more recently than its registry entry was updated THEN the reported time-since-movement is measured from the log [REQ: activity-is-read-from-the-session-log-never-from-a-heartbeat, scenario: last-movement-comes-from-the-log]
- [ ] AC-27: WHEN a registry entry is hours old and the session log is seconds old THEN the agent is reported as recently active [REQ: activity-is-read-from-the-session-log-never-from-a-heartbeat, scenario: a-stale-registry-does-not-make-an-agent-look-idle]

**An outstanding tool call is what "working" means**

- [ ] AC-28: WHEN the log tail holds a tool invocation with no matching result THEN the state is working, naming that tool and how long it has been outstanding [REQ: an-outstanding-tool-call-is-what-working-means, scenario: an-agent-inside-a-tool]
- [ ] AC-29: WHEN the last log entry is an assistant message and no tool call is outstanding THEN the state is waiting [REQ: an-outstanding-tool-call-is-what-working-means, scenario: an-agent-that-finished-its-turn]

**A state that cannot be determined is unknown, never idle**

- [ ] AC-30: WHEN a live process has no session log written yet THEN the agent is listed as running with an unknown state [REQ: a-state-that-cannot-be-determined-is-unknown-never-idle, scenario: a-session-with-no-log-yet]
- [ ] AC-31: WHEN the session log cannot be read THEN the state is unknown and the reason is reported [REQ: a-state-that-cannot-be-determined-is-unknown-never-idle, scenario: an-unreadable-log]
- [ ] AC-32: WHEN a source of state omits the status field entirely rather than leaving it blank THEN the state is unknown, and a test for any particular state SHALL NOT be the thing that decides it [REQ: a-state-that-cannot-be-determined-is-unknown-never-idle, scenario: a-status-field-that-is-absent-not-empty]

**Waiting for a person is a state of its own, and it says what for**

- [ ] AC-33: WHEN the runtime's record reports the session as waiting and names what for THEN the agent is reported as waiting, carrying that reason [REQ: waiting-for-a-person-is-a-state-of-its-own-and-it-says-what-for, scenario: a-waiting-agent-is-reported-as-waiting]
- [ ] AC-34: WHEN the log's tail is inconclusive and the record is absent or stale THEN the state is unknown, not waiting and not idle [REQ: waiting-for-a-person-is-a-state-of-its-own-and-it-says-what-for, scenario: a-waiting-state-is-not-derived-from-the-log-alone]
- [ ] AC-35: WHEN an agent's log has not moved for a long time and the record reports it waiting THEN it is reported as waiting for a person, not as merely still [REQ: waiting-for-a-person-is-a-state-of-its-own-and-it-says-what-for, scenario: waiting-outranks-a-quiet-log]

**What an agent is working towards is read from the engine's record, never guessed**

- [ ] AC-36: WHEN an agent runs in a project the engine drives, and the engine has recorded a run THEN the agent reports what it is working on and how far it has got, from that record [REQ: what-an-agent-is-working-towards-is-read-from-the-engine-s-record-never-guessed, scenario: an-adopted-project-reports-purpose-and-progress]
- [ ] AC-37: WHEN recorded state claims a run in progress whose process is no longer alive THEN it is reported as stale, distinguishably from a live run [REQ: what-an-agent-is-working-towards-is-read-from-the-engine-s-record-never-guessed, scenario: a-stale-run-is-not-reported-as-running]
- [ ] AC-38: WHEN a project has no engine record THEN the agent reports no purpose, and the absence is stated rather than shown as an empty label [REQ: what-an-agent-is-working-towards-is-read-from-the-engine-s-record-never-guessed, scenario: no-engine-no-invented-purpose]
- [ ] AC-39: WHEN progress is reported THEN it is derived from completed tasks, and not from a count of turns or events [REQ: what-an-agent-is-working-towards-is-read-from-the-engine-s-record-never-guessed, scenario: progress-is-completed-work-not-activity]

**A phase is reported only where the agent declared one**

- [ ] AC-40: WHEN an agent declares the phase it is in THEN the surface reports that phase [REQ: a-phase-is-reported-only-where-the-agent-declared-one, scenario: a-declared-phase-is-shown]
- [ ] AC-41: WHEN an agent declares nothing THEN no phase is reported, and none is inferred from its log [REQ: a-phase-is-reported-only-where-the-agent-declared-one, scenario: an-undeclared-phase-produces-no-icon]
- [ ] AC-42: WHEN an agent is known to have spawned another agent THEN its directing role may be reported, because that relation was measured rather than guessed [REQ: a-phase-is-reported-only-where-the-agent-declared-one, scenario: role-is-not-a-phase]

**A declared blockage is independent of the measured state**

- [ ] AC-43: WHEN an agent's measured state is busy and it has declared itself blocked THEN both are reported, and the blockage is visible [REQ: a-declared-blockage-is-independent-of-the-measured-state, scenario: blocked-while-busy]
- [ ] AC-44: WHEN an agent's measured state is waiting and it has declared no blockage THEN no blockage is reported — it may simply have finished a turn [REQ: a-declared-blockage-is-independent-of-the-measured-state, scenario: waiting-is-not-blockage]

**Watching the fleet costs a bounded number of file watchers**

- [ ] AC-45: WHEN the number of running agents doubles THEN the number of watchers the framework holds does not increase [REQ: watching-the-fleet-costs-a-bounded-number-of-file-watchers, scenario: watchers-do-not-scale-with-agents]
- [ ] AC-46: WHEN an agent's log is displayed THEN its content is read on demand rather than by arming a watcher per log [REQ: watching-the-fleet-costs-a-bounded-number-of-file-watchers, scenario: log-content-is-read-not-watched]

**Listing every agent does not read every log in full**

- [ ] AC-47: WHEN the fleet inventory derives state for every discovered agent THEN no session log is read in full [REQ: listing-every-agent-does-not-read-every-log-in-full, scenario: the-list-is-derived-from-metadata-and-tails]
- [ ] AC-48: WHEN a caller opens one agent's log THEN that log alone may be parsed in full [REQ: listing-every-agent-does-not-read-every-log-in-full, scenario: an-opened-log-is-parsed-fully]


### agent-fleet-instruct

**An instruction is delivered over the messaging bus**

- [ ] AC-49: WHEN a caller sends an instruction to an agent that has a bus identity THEN the message is delivered addressed to that specific session, not broadcast to its project [REQ: an-instruction-is-delivered-over-the-messaging-bus, scenario: an-addressed-instruction-reaches-an-agent]
- [ ] AC-50: WHEN the intended agent's identity cannot be resolved THEN the send is refused and the reason reported, rather than sent to everyone in its room [REQ: an-instruction-is-delivered-over-the-messaging-bus, scenario: a-broadcast-is-never-a-substitute-for-an-address]

**The delivery report distinguishes every outcome, and an outcome can expire**

- [ ] AC-51: WHEN the bus reports that the send woke the addressed session THEN the outcome is reported as arriving now [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire, scenario: an-agent-with-a-waiter]
- [ ] AC-52: WHEN the bus reports no session woken and the agent's state is working THEN the outcome is reported as arriving at the end of the current turn [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire, scenario: a-working-agent-without-a-waiter]
- [ ] AC-53: WHEN the bus reports no session woken and the agent's state is not working THEN the outcome is reported as sitting unread until someone types into that session [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire, scenario: an-idle-agent-without-a-waiter]
- [ ] AC-54: WHEN the bus returns no usable answer about what it woke THEN the outcome is reported as unknown, and not as delivered [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire, scenario: an-unknown-outcome-is-not-upgraded-to-success]
- [ ] AC-55: WHEN the send call returns successfully THEN nothing is reported as delivered on that basis alone, and the outcome remains pending until the channel says what became of the message [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire, scenario: the-send-call-s-success-is-not-an-outcome]
- [ ] AC-56: WHEN the channel reports that it did not deliver the message and that someone at the receiving end must approve it first THEN the outcome is reported as held pending that approval, distinctly from delivered and from sitting unread [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire, scenario: a-message-held-for-the-recipient-s-human]
- [ ] AC-57: WHEN a held message expires without the recipient's human answering THEN the lapse is reported where the original outcome was shown, and the message is reported as not delivered [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire, scenario: a-hold-that-lapses]
- [ ] AC-58: WHEN a message is held THEN nothing reports the agent as having been instructed, because the agent has not seen it [REQ: the-delivery-report-distinguishes-every-outcome-and-an-outcome-can-expire, scenario: a-held-message-is-never-counted-as-reaching-the-agent]

**A direct channel may ring the bell, but never carry the message**

- [ ] AC-59: WHEN an instruction is written to the durable channel and the reply reports that no session was woken THEN the framework may prompt that session over the direct channel to read its mailbox [REQ: a-direct-channel-may-ring-the-bell-but-never-carry-the-message, scenario: the-durable-send-woke-nobody]
- [ ] AC-60: WHEN the direct channel is used THEN it carries only a prompt to check the mailbox, never the instruction text [REQ: a-direct-channel-may-ring-the-bell-but-never-carry-the-message, scenario: the-content-never-travels-on-the-direct-channel]
- [ ] AC-61: WHEN the direct channel cannot be used at all THEN delivery still happens through the durable path, and the reported outcome says the message is waiting rather than that it failed [REQ: a-direct-channel-may-ring-the-bell-but-never-carry-the-message, scenario: the-direct-channel-is-unavailable]

**An orphaned waiter is shown, and removing it is an offer rather than a tidy-up**

- [ ] AC-62: WHEN a project holds waiter processes whose sessions have exited THEN they are reported, alongside the agents reported as having no waiter [REQ: an-orphaned-waiter-is-shown-and-removing-it-is-an-offer-rather-than-a-tidy-up, scenario: an-orphan-is-reported-next-to-the-missing-waiter]
- [ ] AC-63: WHEN an orphaned waiter is to be removed THEN it happens only on an action naming that specific process, and never as a side effect of installing a waiter or of any other operation [REQ: an-orphaned-waiter-is-shown-and-removing-it-is-an-offer-rather-than-a-tidy-up, scenario: removal-is-explicit-and-named]
- [ ] AC-64: WHEN a candidate waiter's session is alive, or cannot be determined to be dead THEN it is not offered for removal and not removed [REQ: an-orphaned-waiter-is-shown-and-removing-it-is-an-offer-rather-than-a-tidy-up, scenario: a-live-waiter-is-never-removed]
- [ ] AC-65: WHEN waiter candidates are gathered THEN each is resolved to a process and checked against its session, and no candidate comes from the number of matches a pattern returned [REQ: an-orphaned-waiter-is-shown-and-removing-it-is-an-offer-rather-than-a-tidy-up, scenario: a-candidate-is-an-identity-not-a-match-count]

**An answer to an open decision goes to the connector, not to a session**

- [ ] AC-66: WHEN an open decision is answered from the surface THEN the answer is written to the connector under the change and task it answers [REQ: an-answer-to-an-open-decision-goes-to-the-connector-not-to-a-session, scenario: an-answer-is-keyed-to-what-it-answers]
- [ ] AC-67: WHEN the session that raised the decision has exited THEN the answer is still accepted and recorded [REQ: an-answer-to-an-open-decision-goes-to-the-connector-not-to-a-session, scenario: the-asking-session-no-longer-exists]
- [ ] AC-68: WHEN an answer is recorded THEN the outcome states that it is recorded and awaiting the next run, not that an agent has seen it [REQ: an-answer-to-an-open-decision-goes-to-the-connector-not-to-a-session, scenario: recorded-is-not-received]

**An agent that cannot be instructed says so where the input would be**

- [ ] AC-69: WHEN an agent is discovered in a project where the messaging bus is not installed THEN it appears with its state and log, its input disabled, and the reason stated [REQ: an-agent-that-cannot-be-instructed-says-so-where-the-input-would-be, scenario: an-agent-in-a-project-without-the-bus]
- [ ] AC-70: WHEN no messaging bus is present on the machine THEN discovery and state still work for every agent, and every tile reports instruction as unavailable [REQ: an-agent-that-cannot-be-instructed-says-so-where-the-input-would-be, scenario: the-bus-is-unavailable-entirely]


### agent-fleet-terminal

**A terminal exists only for a process the framework started or adopted**

- [ ] AC-71: WHEN an agent is started from the surface THEN it runs under a framework-owned pseudo-terminal, and a terminal is reported as available [REQ: a-terminal-exists-only-for-a-process-the-framework-started-or-adopted, scenario: a-surface-started-agent-has-a-terminal]
- [ ] AC-72: WHEN an agent process was started outside the framework and has not been adopted THEN no terminal is reported for it, and no write into its terminal is attempted [REQ: a-terminal-exists-only-for-a-process-the-framework-started-or-adopted, scenario: a-foreign-session-has-none]
- [ ] AC-73: WHEN a caller asks whether an agent can be typed into THEN the answer names which of the three populations it is in, rather than leaving the caller to guess from other fields [REQ: a-terminal-exists-only-for-a-process-the-framework-started-or-adopted, scenario: the-reason-is-carried-not-inferred]

**Adoption of a running session is measured before it is relied upon**

- [ ] AC-74: WHEN measurement shows a running session can be resumed into an owned terminal without losing its history THEN adoption is offered for foreign sessions, and the resulting agent reports a terminal [REQ: adoption-of-a-running-session-is-measured-before-it-is-relied-upon, scenario: adoption-works]
- [ ] AC-75: WHEN measurement shows it cannot be done, or cannot be done without losing session state THEN foreign sessions keep the bus input, their tiles state that no terminal is possible, and the finding is written into the design with what was run and what it returned [REQ: adoption-of-a-running-session-is-measured-before-it-is-relied-upon, scenario: adoption-does-not-work]
- [ ] AC-76: WHEN the measurement has not been made THEN the framework behaves as if adoption is impossible, rather than offering a control whose outcome is unknown [REQ: adoption-of-a-running-session-is-measured-before-it-is-relied-upon, scenario: the-unmeasured-state-is-not-the-optimistic-one]

**Resuming a session that is running is refused, not offered**

- [ ] AC-77: WHEN an agent is discovered with a live process bound to its session log THEN no resume or adopt control is offered for it, and the reason given is that the session is running [REQ: resuming-a-session-that-is-running-is-refused-not-offered, scenario: a-live-session-is-not-resumable-from-the-surface]
- [ ] AC-78: WHEN a session log has no live process writing it THEN resuming it is permitted [REQ: resuming-a-session-that-is-running-is-refused-not-offered, scenario: a-dead-session-may-be-resumed]
- [ ] AC-79: WHEN it cannot be determined whether a session is still running THEN it is treated as running and the resume is refused, rather than attempted on the optimistic reading [REQ: resuming-a-session-that-is-running-is-refused-not-offered, scenario: the-refusal-survives-a-stale-binding]

**Starting work goes through the engine's one entry point, not a second spawn path**

- [ ] AC-80: WHEN a work unit is started from the surface THEN the engine's command is invoked, and the run is indistinguishable from an agent-started one except in what recorded who started it [REQ: starting-work-goes-through-the-engine-s-one-entry-point-not-a-second-spawn-path, scenario: the-surface-starts-a-unit]
- [ ] AC-81: WHEN the engine's command is invoked from the surface THEN it runs under the pseudo-terminal the framework owns, so every terminal rule above applies to it unchanged [REQ: starting-work-goes-through-the-engine-s-one-entry-point-not-a-second-spawn-path, scenario: the-terminal-still-belongs-to-the-surface]
- [ ] AC-82: WHEN an interactive session is started with no work unit THEN it is presented as a bare session, and no change, group or verdict field is shown for it — rather than shown empty [REQ: starting-work-goes-through-the-engine-s-one-entry-point-not-a-second-spawn-path, scenario: a-bare-session-is-labelled-as-one]
- [ ] AC-83: WHEN the ways the surface can start an agent are enumerated THEN exactly one of them starts a work unit [REQ: starting-work-goes-through-the-engine-s-one-entry-point-not-a-second-spawn-path, scenario: no-second-start-path-exists]

**Terminal traffic travels in both directions and is never persisted**

- [ ] AC-84: WHEN the agent writes to its terminal THEN the connected browser receives that output [REQ: terminal-traffic-travels-in-both-directions-and-is-never-persisted, scenario: output-reaches-the-browser]
- [ ] AC-85: WHEN a key is typed into the connected terminal component THEN the agent process receives it as terminal input [REQ: terminal-traffic-travels-in-both-directions-and-is-never-persisted, scenario: keystrokes-reach-the-agent]
- [ ] AC-86: WHEN the stream fails or a frame cannot be decoded THEN the diagnostic names the stream and the failure kind, and quotes none of its content [REQ: terminal-traffic-travels-in-both-directions-and-is-never-persisted, scenario: a-failure-reports-shape-not-content]
- [ ] AC-87: WHEN a terminal session ends THEN no transcript of it remains on disk [REQ: terminal-traffic-travels-in-both-directions-and-is-never-persisted, scenario: nothing-is-kept]

**A started agent's lifetime is defined for the browser leaving and the service restarting**

- [ ] AC-88: WHEN the browser showing an agent's terminal closes THEN the agent keeps running, and is still listed with its terminal reattachable [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting, scenario: the-browser-disconnects]
- [ ] AC-89: WHEN a browser reconnects to an agent the framework started THEN it attaches to the same terminal and the agent continues [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting, scenario: reattaching-after-disconnect]
- [ ] AC-90: WHEN the service that started an agent restarts THEN the agent is still running and still instructable, and its terminal alone is reported as gone — never as attachable [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting, scenario: the-service-restarts]
- [ ] AC-91: WHEN any service in the framework restarts, including the one that owns agent lifetime THEN an agent started from the surface keeps running, because it was placed outside that service's lifetime rather than inside it [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting, scenario: an-agent-outlives-the-service-that-started-it]
- [ ] AC-92: WHEN any path would try to take over a terminal by reopening another process's descriptor THEN it is not attempted, and the terminal is reported gone while the agent stays listed and instructable [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting, scenario: a-terminal-handle-is-never-reacquired-from-outside]
- [ ] AC-93: WHEN an agent started here is to be stopped THEN it stops on an explicit action, and never as a consequence of a view being closed [REQ: a-started-agent-s-lifetime-is-defined-for-the-browser-leaving-and-the-service-restarting, scenario: stopping-is-deliberate]

**The terminal is proven by driving it as a person drives it**

- [ ] AC-94: WHEN a key is entered into the terminal component in a browser THEN the agent process receives it, and its response appears in that same component [REQ: the-terminal-is-proven-by-driving-it-as-a-person-drives-it, scenario: a-keystroke-makes-the-round-trip]
- [ ] AC-95: WHEN the tests run against an agent the framework did not start THEN no terminal is offered for it, and this is asserted rather than assumed [REQ: the-terminal-is-proven-by-driving-it-as-a-person-drives-it, scenario: the-negative-case-is-asserted-too]


### agent-fleet-surface

**Projects on the left, the selected project's agents on the right**

- [ ] AC-96: WHEN a project tile is selected THEN that project's agents appear as tiles, one per agent [REQ: projects-on-the-left-the-selected-project-s-agents-on-the-right, scenario: selecting-a-project-shows-its-agents]
- [ ] AC-97: WHEN a selected project holds no live agent THEN the panel says so, and the project remains in the list [REQ: projects-on-the-left-the-selected-project-s-agents-on-the-right, scenario: a-project-with-no-running-agent]

**A project tile carries the state of the agents inside it**

- [ ] AC-98: WHEN any agent in an unselected project is waiting THEN its project's tile shows that, without the project being selected [REQ: a-project-tile-carries-the-state-of-the-agents-inside-it, scenario: a-waiting-agent-is-visible-from-the-project-list]
- [ ] AC-99: WHEN the agent area is compacted for density THEN the count of waiting agents remains readable [REQ: a-project-tile-carries-the-state-of-the-agents-inside-it, scenario: the-counts-stay-visible-when-the-grid-is-compacted]

**A project awaiting a human is surfaced even when no agent is running**

- [ ] AC-100: WHEN a project has work awaiting a human answer and no agent process running THEN its tile reports it as awaiting an answer, not as holding nothing [REQ: a-project-awaiting-a-human-is-surfaced-even-when-no-agent-is-running, scenario: a-stopped-project-with-no-agents-is-not-empty]
- [ ] AC-101: WHEN a project tile shows a waiting count THEN that count includes work awaiting an answer with no agent attached to it [REQ: a-project-awaiting-a-human-is-surfaced-even-when-no-agent-is-running, scenario: the-count-is-of-what-is-waiting-not-of-who-is-present]
- [ ] AC-102: WHEN everything that produced the question has exited and restarted THEN the project is still surfaced as awaiting an answer [REQ: a-project-awaiting-a-human-is-surfaced-even-when-no-agent-is-running, scenario: the-marker-outlives-every-process]

**An agent tile carries state, log excerpt and its own input**

- [ ] AC-103: WHEN an agent is inside a tool THEN the tile names the tool and how long it has been running [REQ: an-agent-tile-carries-state-log-excerpt-and-its-own-input, scenario: a-tile-shows-what-the-agent-is-doing]
- [ ] AC-104: WHEN an agent has ended its turn THEN the tile shows the last lines of its log, so the reason for waiting is readable [REQ: an-agent-tile-carries-state-log-excerpt-and-its-own-input, scenario: a-tile-shows-why-an-agent-is-waiting]
- [ ] AC-105: WHEN the number of agents forces a denser layout THEN each tile still shows its state and its input, with other content shortened instead [REQ: an-agent-tile-carries-state-log-excerpt-and-its-own-input, scenario: density-does-not-remove-state-or-input]
- [ ] AC-106: WHEN an agent's session log was bound heuristically THEN the tile marks the log as unconfirmed [REQ: an-agent-tile-carries-state-log-excerpt-and-its-own-input, scenario: a-tile-whose-binding-is-a-guess-says-so]

**A tile can be enlarged, and the other agents stay visible as rows**

- [ ] AC-107: WHEN an agent tile is enlarged THEN it shows a larger log area and the other agents appear as rows [REQ: a-tile-can-be-enlarged-and-the-other-agents-stay-visible-as-rows, scenario: enlarging-one-tile]
- [ ] AC-108: WHEN a tile is enlarged while another agent is waiting THEN that agent's row shows its waiting state [REQ: a-tile-can-be-enlarged-and-the-other-agents-stay-visible-as-rows, scenario: the-other-agents-are-still-readable]
- [ ] AC-109: WHEN a row is selected THEN that agent becomes the enlarged tile [REQ: a-tile-can-be-enlarged-and-the-other-agents-stay-visible-as-rows, scenario: a-row-is-the-way-back]

**View state is remembered per project**

- [ ] AC-110: WHEN a project is selected, a tile enlarged, another project visited, and the first selected again THEN the same tile is enlarged [REQ: view-state-is-remembered-per-project, scenario: returning-to-a-project-restores-its-view]
- [ ] AC-111: WHEN the remembered enlarged agent is no longer running THEN the grid is shown, and no empty enlarged tile [REQ: view-state-is-remembered-per-project, scenario: a-remembered-agent-that-is-gone]
- [ ] AC-112: WHEN text is typed into an agent's input and another project is visited THEN returning to that project restores the text, unsent [REQ: view-state-is-remembered-per-project, scenario: an-unsent-draft-survives-a-project-switch]
- [ ] AC-113: WHEN a project with exactly one agent is opened for the first time THEN that agent's tile is enlarged, because a grid of one leaves the rest of the area empty [REQ: view-state-is-remembered-per-project, scenario: a-project-holding-one-agent-opens-enlarged]
- [ ] AC-114: WHEN the single tile is collapsed and the project is visited again THEN it stays collapsed — a default may choose the first view, never override a chosen one [REQ: view-state-is-remembered-per-project, scenario: a-remembered-choice-outranks-the-default]

**Dictation writes into the same input as typing**

- [ ] AC-115: WHEN dictation is used on an agent tile THEN the transcript appears in that agent's input, editable before sending [REQ: dictation-writes-into-the-same-input-as-typing, scenario: dictated-text-lands-in-the-input]
- [ ] AC-116: WHEN voice input is not configured THEN typing is unaffected and the dictation control is absent rather than failing on use [REQ: dictation-writes-into-the-same-input-as-typing, scenario: dictation-unavailable]

**The delivery outcome is shown where the message was sent**

- [ ] AC-117: WHEN an instruction is sent to an agent THEN the tile distinguishes arriving now, arriving at the end of the turn, and sitting unread [REQ: the-delivery-outcome-is-shown-where-the-message-was-sent, scenario: each-outcome-reads-differently]
- [ ] AC-118: WHEN the outcome is that the message sits unread because no waiter is running THEN the tile says so, and offers the action that would make that agent wakeable [REQ: the-delivery-outcome-is-shown-where-the-message-was-sent, scenario: an-agent-that-will-not-wake-offers-the-remedy]

**The fleet is the landing screen, and an unfinished answer is not an empty one**

- [ ] AC-119: WHEN the application is opened at its root route THEN the fleet screen is shown [REQ: the-fleet-is-the-landing-screen-and-an-unfinished-answer-is-not-an-empty-one, scenario: the-root-route-renders-the-fleet]
- [ ] AC-120: WHEN the screen paints before discovery has returned THEN it states that it is still looking, and shows neither an empty fleet nor a count of zero [REQ: the-fleet-is-the-landing-screen-and-an-unfinished-answer-is-not-an-empty-one, scenario: discovery-has-not-answered-yet]
- [ ] AC-121: WHEN discovery has completed and found no live agent THEN the screen says that no agent is running, distinctly from the state above [REQ: the-fleet-is-the-landing-screen-and-an-unfinished-answer-is-not-an-empty-one, scenario: discovery-answered-and-there-genuinely-is-nothing]
- [ ] AC-122: WHEN a reader wants the projects overview THEN it is reachable from the navigation, with every behaviour it had before [REQ: the-fleet-is-the-landing-screen-and-an-unfinished-answer-is-not-an-empty-one, scenario: the-projects-overview-is-not-lost]

**An install offered from the screen goes through the module installer, and shows what it did not do**

- [ ] AC-123: WHEN the screen offers to wire a capability into a project THEN it invokes the module installer for the module that provides it, and no capability-specific install path exists on the surface [REQ: an-install-offered-from-the-screen-goes-through-the-module-installer-and-shows-what-it-did-not-do, scenario: the-install-is-the-installer-s-not-the-screen-s]
- [ ] AC-124: WHEN an install leaves files alone because the project modified them THEN each skipped file and its reason appear on the screen, not only in the installer's output [REQ: an-install-offered-from-the-screen-goes-through-the-module-installer-and-shows-what-it-did-not-do, scenario: skips-are-shown-not-swallowed]
- [ ] AC-125: WHEN an install writes no files THEN the screen states that outcome, rather than reporting a plain success [REQ: an-install-offered-from-the-screen-goes-through-the-module-installer-and-shows-what-it-did-not-do, scenario: a-run-that-changed-nothing-says-so]
- [ ] AC-126: WHEN a module requires another that the project does not have THEN the install is refused and the missing requirement is named, and no control offers to proceed regardless [REQ: an-install-offered-from-the-screen-goes-through-the-module-installer-and-shows-what-it-did-not-do, scenario: a-missing-requirement-is-a-refusal-not-a-warning]
- [ ] AC-127: WHEN the screen presents what can be installed into a project THEN a module's machine-wide executable part is not among it [REQ: an-install-offered-from-the-screen-goes-through-the-module-installer-and-shows-what-it-did-not-do, scenario: the-executable-part-is-never-offered-into-a-project]

**A tile offers a terminal only where one can exist, and says why when it cannot**

- [ ] AC-128: WHEN an agent was started from this screen THEN its tile offers a terminal that types into that agent [REQ: a-tile-offers-a-terminal-only-where-one-can-exist-and-says-why-when-it-cannot, scenario: a-surface-started-agent-offers-its-terminal]
- [ ] AC-129: WHEN an agent was started outside the framework and cannot be adopted THEN its tile offers no terminal, states the reason, and keeps its bus input [REQ: a-tile-offers-a-terminal-only-where-one-can-exist-and-says-why-when-it-cannot, scenario: a-foreign-session-offers-no-terminal]
