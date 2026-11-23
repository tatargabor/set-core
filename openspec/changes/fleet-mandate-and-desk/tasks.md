<!--
Ordered by dependency. Group 1 is measurement, not implementation: design D4, D5 and D7 rest on
three carriers that were read from documentation or from a neighbouring measurement, and nothing
in groups 3-5 is built before they are measured on this runtime. Write each result into
`measurements.md` in this directory, with the command and its output.

Layer marking, per .claude/rules/code-quality.md: CORE (lib/set_orch/fleet/, abstract), API
(lib/set_orch/api/), CLI (bin/), WEB (web/). No task puts project-type knowledge into CORE.

Each stage ends in something usable on its own: after group 3 every started agent has a mandate
on its tile; after group 5 an agent reaches another project with one command; group 7 draws it.

Every test written for a fix or a guard is proven with the fix stashed (see the
`evidence-discipline` skill): a test that passes either way proves nothing.
-->

## 1. Measure first — the carriers the design assumes

- [x] 1.1 CORE — Measure that a `SessionStart` hook supplied as a `--settings` JSON string fires for an agent started with the owner's real argv, on each of: first start, `/clear`, compaction, `--resume`. Record which sources fire and what the hook receives. [REQ: the-agent-is-told-its-mandate-at-every-session-start]
- [x] 1.2 CORE — Measure that the hook's subprocess sees an environment variable set on the agent process, and that context the hook prints reaches the session (ask the agent to repeat a planted token). [REQ: the-agent-is-told-its-mandate-at-every-session-start]
- [x] 1.3 CORE — Measure the collision case for `SessionStart` specifically: a project that declares its own session-start hook still has it run beside the framework's, and the project tree is byte-identical before and after (hash every file, hidden ones included). [REQ: the-agent-is-told-its-mandate-at-every-session-start]
- [x] 1.4 CORE — Measure that a positional prompt appended to the owner's argv starts a first turn, and what the agent sees when the session-start context and that prompt arrive together. **DONE under a multiplexer pane with the owner's argv (measurements.md M3); the owner's own pty and scope are exercised in 9.1, because the owner cannot take the addition before 3.1.** [REQ: the-desk-is-started-when-none-is-live]
- [x] 1.5 CORE — Measure, in a bus-enrolled project, how long a freshly started agent takes to appear with a seat keyed by its session id in the bus's machine-readable agent list (ten starts; report the distribution). The readiness bound in 4.3 is set from this, not guessed. [REQ: a-request-that-cannot-have-a-desk-is-refused-with-the-reason]
- [x] 1.6 CORE — Capture, from the bus's own writer, the JSON a send returns (room and timestamp fields) and the heading of a linked reply, and store both as test fixtures containing no real message text. [REQ: an-engagement-is-answered-only-by-a-reply-the-bus-links-to-it]
- [x] 1.7 CORE — Measure how "this project is enrolled on the bus" can be decided before a start (the bus doctor's machine-readable output, or the project's hook configuration), and which way each candidate fails. [REQ: a-request-that-cannot-have-a-desk-is-refused-with-the-reason]

## 2. The mandate record (CORE)

- [ ] 2.1 CORE — `lib/set_orch/fleet/mandate.py`: the record (id, kind, goal, scope, done_when, requester with is_claim, project, cwd, label, unit, session_ids, source, delivered, declared_at, ended) and its store under the per-user state directory — atomic write, file lock, owner-only permissions, bounded retention of ended records. [REQ: a-mandate-is-recorded-in-the-act-of-starting]
- [ ] 2.2 CORE — Join a mandate to a live agent by an identity measured from the running process (the mandate id in its environment), then by unit, then by recorded session id; append each newly observed session id to the record. [REQ: a-mandate-is-recorded-in-the-act-of-starting]
- [ ] 2.3 CORE — Mark a mandate ended with a reason (`stopped`, `ended`, `desk-quiet`) when its agent stops or its process is gone, keep it readable, and never write a "fulfilled" value. [REQ: an-ended-mandate-is-kept-and-never-called-fulfilled]
- [ ] 2.4 CORE — `restore.py`: a restored agent continues the mandate its recorded session held; the record lists the new session. [REQ: the-mandate-is-carried-across-a-restore]
- [ ] 2.5 CORE — Logging: ids, kinds and outcome classes only. A test plants a marker string in a goal and asserts it appears in no log record and in no exception message. [REQ: mandate-text-is-never-logged-and-never-enters-a-repository]
- [ ] 2.6 CORE — Unit tests for the store (concurrent writers, a truncated file, permissions, retention) and for the join (owner restarted, unit renamed, process gone). [REQ: a-mandate-is-recorded-in-the-act-of-starting]

## 3. Start, declare, deliver (CORE, API, CLI)

- [ ] 3.1 CORE — `owner.py` / `ownerd.py` / `protocol.py`: the start request takes one typed `mandate_id` and a kind; the owner sets the mandate id and the label in the child's environment, adds the framework's `--settings` hook, and appends the opening line for the kind (D5). A test asserts the owner still writes no file and accepts no free-form argv or environment. [REQ: the-agent-is-told-its-mandate-at-every-session-start]
- [ ] 3.2 API — `StartAgentBody.mandate` (goal, kind, scope, done_when), typed and still `extra="forbid"`. Write the record before calling the owner; remove it if the owner refuses. Refuse a request that has a requester and no goal. [REQ: an-agent-requested-start-without-a-goal-is-refused]
- [ ] 3.3 API — Declare a mandate for an agent that has none, by label or by session id; report `delivered` truthfully (true only for an agent started with the carrier, after its next session start). [REQ: a-mandate-can-be-declared-later-and-says-whether-the-agent-was-told]
- [ ] 3.4 CLI — `bin/set-fleet-mandate`: `hook` (reads the mandate named in the environment and prints it as session-start context; prints nothing and exits 0 when there is none), `show`, `declare`. [REQ: the-agent-is-told-its-mandate-at-every-session-start]
- [ ] 3.5 CORE — The delivered text: goal, kind, scope, requester, closing condition, and the standing rule for outside requests naming the desk and `set-fleet-ask`. One template, tested for each kind. [REQ: the-standing-rule-for-outside-requests-is-an-instruction-and-is-reported-as-one]
- [ ] 3.6 API — The inventory carries `mandate` per agent, or its absence with a reason (`not-started-here`, `not-declared`); nothing is derived from label, transcript, focus or directory. [REQ: an-agent-without-a-mandate-is-reported-as-having-none]
- [ ] 3.7 API — `parent` is read from the mandate when the owner no longer holds the agent, with the source `recorded`. [REQ: the-mandate-carries-who-asked-and-marks-it-as-a-claim]
- [ ] 3.8 API — Tests for 3.2, 3.3, 3.6 and 3.7 against a fake owner, including the owner-restart case. [REQ: a-mandate-is-recorded-in-the-act-of-starting]

## 4. The desk (CORE, API)

- [ ] 4.1 CORE — `lib/set_orch/fleet/desk.py`: resolve a project to the live, framework-held agent whose open mandate has kind `desk`; never consider any other session. [REQ: a-project-request-resolves-to-the-project-s-desk-and-to-no-other-session]
- [ ] 4.2 CORE — Start a desk when none is live: project root from the registry, label `<project>-desk`, `desk` mandate with the requester, the desk opening line. A held-label refusal from the owner is treated as "the desk exists" and re-resolved. [REQ: the-desk-is-started-when-none-is-live]
- [ ] 4.3 CORE — Refusals before any start: unknown project, archived project, failed start-location check, not on the bus (the bus doctor's `hooks.session-start`, measurements.md M6), never trusted by the runtime (M3), and `unmeasured` when either of the last two cannot be read. After a start: wait for the desk's bus seat up to 60 seconds (M4), then fail with `desk-not-ready`. [REQ: a-request-that-cannot-have-a-desk-is-refused-with-the-reason]
- [ ] 4.4 API — Reserve the desk label: refuse renaming a desk, and refuse a non-desk start or rename that takes a registered project's desk label. [REQ: the-desk-label-is-reserved]
- [ ] 4.5 CORE — The quiet sweep, run from the dashboard service's lifespan: stop a desk with no resolving or open engagement whose state and last movement are both measured and past the bound; keep it when anything is unmeasured; end the mandate with `desk-quiet`. Bound from a config key, default thirty minutes. Log the label, the pid and the measured idle time. [REQ: a-quiet-desk-stops-and-an-unmeasured-one-is-kept]
- [ ] 4.6 API — `POST /api/fleet/desks/resolve`: resolution as one call, returning the engagement id, the desk (label, seat, whether it was started) or the refusal reason. [REQ: the-desk-is-started-when-none-is-live]
- [ ] 4.7 CORE — Tests: live desk found, working sessions ignored, concurrent resolution yields one start, each refusal, the three sweep cases. [REQ: a-project-request-resolves-to-the-project-s-desk-and-to-no-other-session]

## 5. Engagements (CORE, API, CLI)

- [ ] 5.1 CORE — `lib/set_orch/fleet/engagement.py`: the record (id, asker seat and mandate, addressed project and desk, kind, subject, room, timestamp, state, reason class, times) and its store beside the mandate store, same write discipline. No field can hold request or reply text. [REQ: an-engagement-stores-a-pointer-and-never-the-request]
- [ ] 5.2 CORE — Closure from the bus: parse entry headings only, in the engagement's room, for an entry by a seat of the addressed project that links to the request's timestamp. Built on the fixtures from 1.6. A test plants a marker in an entry body and asserts it reaches no payload and no log. [REQ: an-engagement-is-answered-only-by-a-reply-the-bus-links-to-it]
- [ ] 5.3 CORE — The waiting bound (a display state, default from config) and the per-asker bound on resolving-or-open engagements (default five), refused with the list of what is open. [REQ: open-engagements-per-asker-are-bounded]
- [ ] 5.4 API — Routes: report an engagement as sent (room, timestamp) or failed (reason class); list engagements filtered by asker, addressed project or state; report states as unmeasured when the bus store cannot be read. [REQ: engagements-can-be-listed-by-the-asker-and-the-screen]
- [ ] 5.5 CLI — `bin/set-fleet-ask <project> "<request>" [--subject …] [--question]`: find the asker's own seat from its session id, resolve, send on the bus as the asker addressed to the desk's seat, report the entry back, print the engagement id and the desk; `--list` shows the asker's engagements. Non-zero exit with the reason on every failure path. [REQ: asking-a-project-is-one-command-that-sends-as-the-asker]
- [ ] 5.6 CORE — An engagement open past the bound is listed as waiting with its age, state unchanged. [REQ: an-engagement-open-past-the-bound-is-reported-as-waiting]
- [ ] 5.7 CLI — Tests for `set-fleet-ask` against a fake API and a fake bus: success, bus refusal, resolution refusal, the bound. [REQ: asking-a-project-is-one-command-that-sends-as-the-asker]

## 6. The role rule learns the flows (CORE)

- [ ] 6.1 CORE — `project_roles.py`: read an optional `flows` list per project (`to`, `what`, `how`), declared once on the side it starts from. [REQ: the-role-file-may-declare-flows-between-projects]
- [ ] 6.2 CORE — Render a "Reaching other projects" section in the generated rule: each outgoing and incoming flow, and the `set-fleet-ask` command; apply the existing visibility rule (a private neighbour is counted, not named, in a public repository's rule). Present even when no flow is declared. [REQ: the-generated-rule-tells-the-agent-how-to-reach-a-neighbour]
- [ ] 6.3 CORE — `set-project roles --check` warns about a flow whose target is not registered, and generation skips that flow. [REQ: the-role-file-may-declare-flows-between-projects]
- [ ] 6.4 CORE — Update `templates/project-roles.example.yaml` with a neutral flows example, and the tests for 6.1-6.3 including the public/private case. [REQ: the-generated-rule-tells-the-agent-how-to-reach-a-neighbour]

## 7. The start form, the tile and the corrected claim (WEB)

- [ ] 7.1 WEB — The start form gains a goal field (and scope, closing condition behind a disclosure that floats, not pushes); an empty goal is allowed and the form says the agent will have no mandate. [REQ: an-agent-requested-start-without-a-goal-is-refused]
- [ ] 7.2 WEB — The agent tile shows the mandate's kind and goal in one line, or "no mandate" with its reason and a control to declare one; after a declaration it says whether the agent was told. [REQ: a-mandate-can-be-declared-later-and-says-whether-the-agent-was-told]
- [ ] 7.3 WEB — `web/src/lib/fleetLineage.ts`: a recorded requester is a claim and a process ancestor is measured; update the notes and the tests that assert the reversed marking, in the same commit. [REQ: the-mandate-carries-who-asked-and-marks-it-as-a-claim]
- [ ] 7.4 WEB — Wherever the screen describes how an agent treats outside requests, it says "instructed to decline", never "blocked". [REQ: the-standing-rule-for-outside-requests-is-an-instruction-and-is-reported-as-one]

## 8. The map (API, WEB)

- [ ] 8.1 API — `GET /api/fleet/map`: project groups (expanded only with a live agent or an open engagement), agent nodes with mandate, and `engagement`, `started` and `flow` relations; a `sources` block naming what could not be read. Role text and flow text are display-only and never logged. [REQ: the-map-payload-carries-projects-agents-and-three-kinds-of-relation]
- [ ] 8.2 WEB — `web/src/lib/fleetMap.ts`: a pure function from the payload to nodes, edges, markers and the two counts, with unit tests — including the unmeasured-source cases. [REQ: a-source-that-could-not-be-read-is-reported-and-not-drawn-as-empty]
- [ ] 8.3 WEB — `FleetMap.tsx` as a dockable view on the node-graph library already in the bundle: project groups, agent nodes with kind and goal, three edge styles that differ without opening anything, the claim marking on start relations. [REQ: the-three-relation-kinds-are-drawn-so-they-cannot-be-confused]
- [ ] 8.4 WEB — Markers: "no mandate" on the node, waiting or failed on the edge with its age, and both counts on the control that opens the map. [REQ: a-missing-mandate-and-an-unanswered-engagement-are-marked-where-the-reader-stands]
- [ ] 8.5 WEB — Node and edge detail as a floating, closable overlay; a test asserts the map container's size and the positions of the other nodes are unchanged by opening it. [REQ: a-detail-opens-above-the-layout]
- [ ] 8.6 WEB — `pnpm build` in `web/`, and type-check with `tsc -b` (plain `tsc --noEmit` measures nothing in this tree). [REQ: the-three-relation-kinds-are-drawn-so-they-cannot-be-confused]
- [ ] 8.7 WEB — Visual check in the browser against the running dashboard: the start form, a tile with and without a mandate, the map with at least one engagement of each state. Say what is seen. If the browser cannot be reached this task stays OPEN and is reported as such. [REQ: a-missing-mandate-and-an-unanswered-engagement-are-marked-where-the-reader-stands]

## 9. Proof on a live machine, and what is handed on

- [ ] 9.1 CORE — End to end, on the real services: from an agent in one enrolled project, `set-fleet-ask` a second enrolled project that has no live session. Observe the desk start, the request arrive, the linked reply, the engagement turn `answered`, and the desk stop after the bound. Record commands and outputs in `measurements.md`. [REQ: asking-a-project-is-one-command-that-sends-as-the-asker]
- [ ] 9.2 CORE — Reconcile `agent-goal-and-lifecycle` with `/opsx:update`: its tasks and acceptance criteria tagged with the five moved requirements are removed or re-pointed at the mandate record, and its closure and rotation text reads "mandate". [REQ: a-mandate-is-recorded-in-the-act-of-starting]
- [ ] 9.3 CORE — Send the four requests of design D9 to the bus project as one addressed request each, pointing at this change's `design.md`. Record the entry timestamps here. [REQ: a-project-request-resolves-to-the-project-s-desk-and-to-no-other-session]
- [ ] 9.4 CORE — Tell whoever maintains the machine's role file that `flows` is now read, and regenerate the role rules (`set-project roles`, then `--check`). [REQ: the-generated-rule-tells-the-agent-how-to-reach-a-neighbour]
- [ ] 9.5 CORE — Restart the agent owner when no agent it holds is working, and the dashboard; confirm each service's start time is later than the commit it must be running. [REQ: the-agent-is-told-its-mandate-at-every-session-start]
- [ ] 9.6 CORE — Add `set-fleet-ask` and `set-fleet-mandate` to the capability guide. [REQ: asking-a-project-is-one-command-that-sends-as-the-asker]

## Acceptance Criteria (from spec scenarios)

### agent-mandate-record

- [ ] AC-1: WHEN an agent is started through the fleet with a goal THEN a mandate record with that goal, kind `work`, the label and the requester exists in the store, and the inventory reports it on that agent [REQ: a-mandate-is-recorded-in-the-act-of-starting, scenario: a-start-with-a-goal-leaves-a-record]
- [ ] AC-2: WHEN the agent owner is restarted while an agent with a mandate keeps running THEN the inventory still reports the same mandate for that agent [REQ: a-mandate-is-recorded-in-the-act-of-starting, scenario: the-record-outlives-the-owner]
- [ ] AC-3: WHEN a start request carries a requester seat and an empty goal THEN the request is refused with a reason naming the missing goal, and no agent is started [REQ: an-agent-requested-start-without-a-goal-is-refused, scenario: an-agent-asks-for-a-peer-without-saying-why]
- [ ] AC-4: WHEN the start form is submitted with an empty goal and no requester THEN the agent is started and the inventory reports it as having no mandate, with the reason `not-declared` [REQ: an-agent-requested-start-without-a-goal-is-refused, scenario: the-person-starts-a-terminal-without-a-goal]
- [ ] AC-5: WHEN an agent the framework did not start is listed THEN its mandate is reported as absent with the reason `not-started-here` [REQ: an-agent-without-a-mandate-is-reported-as-having-none, scenario: a-hand-opened-agent]
- [ ] AC-6: WHEN an agent with no mandate record has a descriptive label THEN the inventory reports no mandate and no goal text taken from the label [REQ: an-agent-without-a-mandate-is-reported-as-having-none, scenario: a-label-that-looks-like-a-goal]
- [ ] AC-7: WHEN a mandate is declared for an agent the framework did not start THEN the record exists with source `declared` and `delivered` false, and the screen says the agent has not been told [REQ: a-mandate-can-be-declared-later-and-says-whether-the-agent-was-told, scenario: declaring-for-a-hand-opened-agent]
- [ ] AC-8: WHEN a mandate is declared for an agent started with the framework's session-start carrier THEN the mandate is delivered at that agent's next session start and `delivered` becomes true [REQ: a-mandate-can-be-declared-later-and-says-whether-the-agent-was-told, scenario: declaring-for-a-framework-started-agent]
- [ ] AC-9: WHEN an agent is started with a mandate THEN its session-start context contains the mandate's goal and the standing rule [REQ: the-agent-is-told-its-mandate-at-every-session-start, scenario: first-start]
- [ ] AC-10: WHEN the agent's session is cleared THEN the new session's session-start context contains the same mandate [REQ: the-agent-is-told-its-mandate-at-every-session-start, scenario: after-a-clear]
- [ ] AC-11: WHEN the project declares its own session-start hook THEN that hook still runs for an agent the framework starts [REQ: the-agent-is-told-its-mandate-at-every-session-start, scenario: the-project-s-own-hooks]
- [ ] AC-12: WHEN an agent has been started with a mandate and has completed its first turn THEN no file in the project's tree was added or changed by the carrier [REQ: the-agent-is-told-its-mandate-at-every-session-start, scenario: the-project-s-tree]
- [ ] AC-13: WHEN a `work` mandate is delivered THEN the text names the project's desk and the command for reaching a project [REQ: the-standing-rule-for-outside-requests-is-an-instruction-and-is-reported-as-one, scenario: the-delivered-text-names-the-desk]
- [ ] AC-14: WHEN the screen describes how an agent treats outside requests THEN it describes an instruction given to the agent, not a block [REQ: the-standing-rule-for-outside-requests-is-an-instruction-and-is-reported-as-one, scenario: the-screen-does-not-overstate-it]
- [ ] AC-15: WHEN the owner has restarted and an agent with a recorded requester is listed THEN its parent relation is still reported, with the source `recorded` [REQ: the-mandate-carries-who-asked-and-marks-it-as-a-claim, scenario: the-requester-after-an-owner-restart]
- [ ] AC-16: WHEN an agent's parent comes from the recorded requester THEN the screen marks it as a claim and does not label it measured [REQ: the-mandate-carries-who-asked-and-marks-it-as-a-claim, scenario: the-screen-s-marking]
- [ ] AC-17: WHEN a recorded session with a mandate is restored THEN the restored agent reports the same mandate id and goal [REQ: the-mandate-is-carried-across-a-restore, scenario: restoring-an-agent-that-had-a-mandate]
- [ ] AC-18: WHEN an agent with a mandate is stopped THEN the mandate is marked ended with the reason `stopped` and is still readable [REQ: an-ended-mandate-is-kept-and-never-called-fulfilled, scenario: the-agent-is-stopped]
- [ ] AC-19: WHEN a start with a goal is logged THEN the log line contains the mandate id and kind and none of the goal's text [REQ: mandate-text-is-never-logged-and-never-enters-a-repository, scenario: a-start-is-logged]
- [ ] AC-20: WHEN the mandate store is first written THEN the file is readable and writable by its owner only [REQ: mandate-text-is-never-logged-and-never-enters-a-repository, scenario: the-store-s-permissions]

### project-desk

- [ ] AC-21: WHEN a request is resolved for a project whose desk is live THEN that desk is returned and no agent is started [REQ: a-project-request-resolves-to-the-project-s-desk-and-to-no-other-session, scenario: a-live-desk-exists]
- [ ] AC-22: WHEN a request is resolved for a project that has live `work` agents and no desk THEN none of those agents is returned [REQ: a-project-request-resolves-to-the-project-s-desk-and-to-no-other-session, scenario: only-working-sessions-are-live]
- [ ] AC-23: WHEN a request is resolved for a registered project with no live desk THEN an agent is started in that project's root with a `desk` mandate and the desk label, and is returned once it has a bus seat [REQ: the-desk-is-started-when-none-is-live, scenario: no-desk-is-live]
- [ ] AC-24: WHEN two requests for the same project are resolved concurrently and no desk is live THEN exactly one desk is started and both requests resolve to it [REQ: the-desk-is-started-when-none-is-live, scenario: two-requests-at-once]
- [ ] AC-25: WHEN a request is resolved for an archived project THEN it is refused with the reason `archived` and no agent is started [REQ: a-request-that-cannot-have-a-desk-is-refused-with-the-reason, scenario: an-archived-project]
- [ ] AC-26: WHEN a request is resolved for a project with no bus hooks installed THEN it is refused with the reason `not-on-bus`, naming enrolment as the fix, and no agent is started [REQ: a-request-that-cannot-have-a-desk-is-refused-with-the-reason, scenario: a-project-that-is-not-on-the-bus]
- [ ] AC-27: WHEN a started desk has no bus seat when the bound elapses THEN the request fails with the class `desk-not-ready` [REQ: a-request-that-cannot-have-a-desk-is-refused-with-the-reason, scenario: a-desk-that-never-becomes-reachable]
- [ ] AC-58: WHEN a request is resolved for a project whose folder has no recorded trust decision THEN it is refused with the reason `not-trusted` and no agent is started [REQ: a-request-that-cannot-have-a-desk-is-refused-with-the-reason, scenario: a-folder-the-runtime-was-never-trusted-in]
- [ ] AC-28: WHEN a rename is requested for a desk THEN it is refused [REQ: the-desk-label-is-reserved, scenario: renaming-a-desk]
- [ ] AC-29: WHEN a `work` agent is started with a registered project's desk label THEN the start is refused [REQ: the-desk-label-is-reserved, scenario: taking-a-desk-label]
- [ ] AC-30: WHEN a desk has no open engagement and has been measured quiet for longer than the bound THEN it is stopped and its mandate is marked ended with the reason `desk-quiet` [REQ: a-quiet-desk-stops-and-an-unmeasured-one-is-kept, scenario: a-desk-with-nothing-open]
- [ ] AC-31: WHEN a desk has an open engagement and has been quiet for longer than the bound THEN it is kept [REQ: a-quiet-desk-stops-and-an-unmeasured-one-is-kept, scenario: a-desk-with-an-open-engagement]
- [ ] AC-32: WHEN a desk's last movement cannot be measured THEN it is kept [REQ: a-quiet-desk-stops-and-an-unmeasured-one-is-kept, scenario: a-desk-whose-movement-is-unmeasured]

### agent-engagement-record

- [ ] AC-33: WHEN an agent runs the command for a project whose desk is reachable THEN a bus entry from the asker's seat addressed to the desk's seat exists, and an engagement in the state `open` points at it [REQ: asking-a-project-is-one-command-that-sends-as-the-asker, scenario: a-request-reaches-a-desk]
- [ ] AC-34: WHEN the bus send fails after the desk was resolved THEN the engagement is marked `failed` with a reason class and the command exits non-zero [REQ: asking-a-project-is-one-command-that-sends-as-the-asker, scenario: the-bus-refuses-the-send]
- [ ] AC-35: WHEN resolution refuses or fails THEN nothing is sent on the bus, the engagement is marked `failed` with the resolution's reason, and the command prints that reason [REQ: asking-a-project-is-one-command-that-sends-as-the-asker, scenario: the-desk-cannot-be-resolved]
- [ ] AC-36: WHEN an engagement is recorded for a request THEN the record contains the request's room and timestamp and does not contain its text [REQ: an-engagement-stores-a-pointer-and-never-the-request, scenario: what-is-stored]
- [ ] AC-37: WHEN the desk writes an entry that links to the request THEN the engagement becomes `answered` and records the reply's timestamp [REQ: an-engagement-is-answered-only-by-a-reply-the-bus-links-to-it, scenario: a-linked-reply]
- [ ] AC-38: WHEN the addressed project writes an entry in the room that does not link to the request THEN the engagement stays `open` [REQ: an-engagement-is-answered-only-by-a-reply-the-bus-links-to-it, scenario: an-unlinked-entry]
- [ ] AC-39: WHEN engagement states are computed THEN only entry headings are parsed, and no text from an entry body appears in any payload or log [REQ: an-engagement-is-answered-only-by-a-reply-the-bus-links-to-it, scenario: bodies-are-never-read]
- [ ] AC-40: WHEN an engagement has been open longer than the bound THEN it is listed as waiting with its age, and its state is still `open` [REQ: an-engagement-open-past-the-bound-is-reported-as-waiting, scenario: a-request-nobody-answered]
- [ ] AC-41: WHEN an asker at the bound runs the command again THEN the request is refused, nothing is started or sent, and the refusal lists the open engagements [REQ: open-engagements-per-asker-are-bounded, scenario: one-request-too-many]
- [ ] AC-42: WHEN an agent lists its engagements THEN it sees each one's addressed project, subject, state and age [REQ: engagements-can-be-listed-by-the-asker-and-the-screen, scenario: the-asker-s-own-list]
- [ ] AC-43: WHEN engagement states are requested while the bus store is unreadable THEN the states are reported as unmeasured with the reason [REQ: engagements-can-be-listed-by-the-asker-and-the-screen, scenario: the-bus-cannot-be-read]

### fleet-relation-map

- [ ] AC-44: WHEN the map is requested while an agent with a mandate is live THEN the payload contains that agent in its project group with the mandate's kind and goal [REQ: the-map-payload-carries-projects-agents-and-three-kinds-of-relation, scenario: an-agent-with-a-mandate]
- [ ] AC-45: WHEN an engagement is open between an asker and a desk THEN the payload contains an `engagement` relation between those two agents with the state `open` and its age [REQ: the-map-payload-carries-projects-agents-and-three-kinds-of-relation, scenario: an-open-engagement]
- [ ] AC-46: WHEN a registered project has no live agent and no open engagement THEN it appears as a collapsed group [REQ: the-map-payload-carries-projects-agents-and-three-kinds-of-relation, scenario: an-idle-project]
- [ ] AC-47: WHEN the reader looks at the map THEN an engagement, a start relation and a declared flow are distinguishable without opening a detail [REQ: the-three-relation-kinds-are-drawn-so-they-cannot-be-confused, scenario: reading-a-relation]
- [ ] AC-48: WHEN one agent has no mandate and one engagement is waiting while the map view is not open THEN the control that opens the map shows both counts [REQ: a-missing-mandate-and-an-unanswered-engagement-are-marked-where-the-reader-stands, scenario: the-map-is-closed]
- [ ] AC-49: WHEN an engagement is waiting THEN its edge is marked and shows its age [REQ: a-missing-mandate-and-an-unanswered-engagement-are-marked-where-the-reader-stands, scenario: an-unanswered-engagement-on-the-map]
- [ ] AC-50: WHEN the reader opens an agent's detail THEN it appears above the map, nothing else moves, and it has a control to close it [REQ: a-detail-opens-above-the-layout, scenario: opening-a-node]
- [ ] AC-51: WHEN the map is requested while the bus store cannot be read THEN the payload marks engagement states as unmeasured and the view says so [REQ: a-source-that-could-not-be-read-is-reported-and-not-drawn-as-empty, scenario: the-bus-is-unreachable]
- [ ] AC-52: WHEN no role file exists on the machine THEN the map shows no declared flows and states that none are declared [REQ: a-source-that-could-not-be-read-is-reported-and-not-drawn-as-empty, scenario: no-role-file]

### project-role-rule

- [ ] AC-53: WHEN a project's entry declares a flow to another registered project THEN the flow is read with its target, its subject and its manner [REQ: the-role-file-may-declare-flows-between-projects, scenario: a-project-with-a-flow]
- [ ] AC-54: WHEN a flow names a project that is not in the registry THEN the role check reports it as a warning and the rule is still generated without that flow [REQ: the-role-file-may-declare-flows-between-projects, scenario: a-flow-to-an-unregistered-project]
- [ ] AC-55: WHEN the rule is generated for a project that declares flows THEN it contains each flow's subject and target, and the command for asking a project [REQ: the-generated-rule-tells-the-agent-how-to-reach-a-neighbour, scenario: a-rule-with-flows]
- [ ] AC-56: WHEN the rule is generated for a public repository whose flow goes to a private project THEN the private project is counted and its name does not appear [REQ: the-generated-rule-tells-the-agent-how-to-reach-a-neighbour, scenario: a-public-repository-with-a-private-neighbour]
- [ ] AC-57: WHEN the rule is generated for a project that declares no flows and is reached by none THEN the rule still contains the command for asking a project [REQ: the-generated-rule-tells-the-agent-how-to-reach-a-neighbour, scenario: a-project-with-no-flows]
