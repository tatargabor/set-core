# Adversarial review — fleet-view

Run 2026-08-17, after the planning artifacts were complete and before any task was started.
Two independent branches, as `adversarial-spec-review` requires: neither reviewer wrote the plan,
and neither saw the other's findings.

**Result: 26 findings — 0 CRITICAL, 15 MAJOR, 11 MINOR.** *(Updated 2026-08-17 after the user
answered D-1: CB-1 answered, RB-3 resolved. 24 open.)* No finding blocks by severity. Fifteen
are MAJOR and several change the shape of the work, so the honest reading is that the plan is not
ready to apply, not that it is cleared.

**Two decisions belong to the user. One (D-1) was answered the same day and is written into the
plan; one (D-2) is still open with the user's direction recorded** — see *Decisions for the user*.

⚠ Every process path in this file is generalised. The measurements ran on a machine holding
consumer projects, and this repository is public.

---

## Decisions for the user

**D-1 — a surface-started agent and the service restart. ANSWERED 2026-08-17.** The service unit
runs with `KillMode=control-group`, so a child the service spawns dies with it;
`start_new_session=True` changes the process group but not the cgroup. *(Raised by the code branch,
CB-1.)*

**Answer: separate the agent-owning process from the web service** — one service for UI and API,
another owning agent lifecycle, the two communicating. The user noted the pattern already exists
here, and it does: a per-project supervisor daemon with its own entry point already owns and
monitors the orchestrator subprocess.

Recorded with the qualification the answer needs, because the split alone does not deliver the
property: it moves the boundary rather than removing it, since the *agent-owning* service kills its
own agents' cgroup on its own restart by the same mechanism. So each agent is additionally started
in its own transient scope — measured to land as a **sibling** of the service under `app.slice`, not
a child — which makes it survive a restart of either service and turns "stopping is deliberate" from
a convention into a named unit. Written up as design §6.2, tasks 5.8 and 5.9.

This also resolves **RB-3**: the two scenarios that reported a surviving agent as unreachable are
now correct in the other direction, and task 5.5's claim — false when written — is true under this
decision.

**D-2 — where a waiting agent below the fold is marked. STILL OPEN; the user's direction is
recorded so it is not re-derived.** The landing screen is a scrollable column and the registry holds
39 projects. *(RB-6.)*

The direction: projects should be **manually orderable** (dragged up and down); a project stays in
the list when its agents are closed; hiding or parking a project low is wanted; and above all a
**workspace** concept — a selector or a set of checkboxes at the top choosing which group of
projects is in view. The user asked to think further about which of these is best, so nothing is
settled.

**One constraint binds whichever option wins, and it is the constraint that produced this decision
in the first place:** manual ordering, hiding and workspaces are all *user-controlled arrangement*,
so each is a place a waiting agent can sit while the screen looks calm — the exact case
`ui-quality.md` puts above the rest. Whatever is chosen, the hiding control itself must carry the
marker: a count on the workspace tab, a marker on the parked section. That is an additional
requirement on the option, not an argument against any of them.

---

## Code branch — findings

Derived from the source, not from the change's artifacts.

### CB-1 [MAJOR] A surface-started agent does not survive a service restart, so task 5.5's promise is false
- **Source:** `templates/systemd/set-web.service:6-13` (no `KillMode=`, `Restart=always`); the live
  unit reports `KillMode=control-group`. Every existing spawn uses `start_new_session=True`
  (`lib/set_orch/api/actions.py:148-155`, `lib/set_orch/manager/supervisor.py:247`,
  `lib/set_orch/supervisor/daemon.py:397`) — that changes the process group, not the cgroup.
- **Failure scenario:** an agent is started from the fleet screen and joins the service's cgroup. A
  restart — including the automatic one after any crash — SIGTERMs the whole cgroup, so the agent
  dies mid-turn while the screen reports "running, no terminal" for a process that no longer exists.
- **Plan location:** tasks 5.4–5.6, AC-76, AC-78; `proposal.md` Impact.
- **Note:** the repository's own memory already records this class for the sentinel subprocess.
- **Status:** **ANSWERED** — see D-1. The plan now separates the agent-owning service and starts
  each agent in its own transient scope (design §6.2, tasks 5.8/5.9); task 5.5's claim becomes true.

### CB-2 [MAJOR] Discovery by process identity lists a non-agent process that runs the same binary
- **Source:** measured live — a process whose `exe` is the same CLI binary that backs all 15 real
  interactive sessions, with cmdline `… --chrome-native-host` and a cwd under the runtime's own
  config directory.
- **Failure scenario:** task 2.1 forbids leaning on the command line, so the browser
  native-messaging host is indistinguishable from an agent by exe + cwd. It becomes an agent tile;
  its cwd is not a git repository, so AC-14 turns that directory into a phantom project tile holding
  one permanently `unknown` agent with an input line that can never deliver.
- **Plan location:** task 2.1, AC-1, AC-14; `design.md` §1.
- **Status:** open

### CB-3 [MAJOR] The union ignores `archived`, which the registry, the API and the current screen all honour
- **Source:** `lib/set_orch/api/projects.py:24-37` (`include_archived=False`, count exported as a
  header), `web/src/pages/Manager.tsx:80-87` (archived behind a toggle),
  `lib/set_orch/project_registry.py:25-31`. Measured: 39 registry entries, **19 archived**.
- **Failure scenario:** task 2.4 unions the sources and AC-7 forbids dropping a registered project
  with no agents, so the landing screen renders 39 tiles, 19 of them dead run directories — and the
  screen built to be more readable than the current one is less so.
- **Plan location:** task 2.4, AC-6/7/8; `design.md` §5.3.
- **Status:** open

### CB-4 [MAJOR] Four hard-coded `/` call sites and the sidebar's Overview entry all resolve to the landing screen
- **Source:** `web/src/App.tsx:216` (the projects overview has **no other route**), `:247` (`/set` →
  `/`), `:249` (`/manager` → `/`), `:254` (catch-all → `/`),
  `web/src/lib/sidebarRegistry.ts:126-132` (global `Overview`, `route: '/'`),
  `web/src/components/UnifiedSidebar.tsx:119` and `:234`.
- **Failure scenario:** after task 7.10 every legacy redirect and the catch-all land on the fleet
  instead of the project list — a behaviour change for bookmarked links the plan does not mention —
  and the sidebar's "Overview" points at the fleet while claiming to be the overview.
- **Plan location:** `proposal.md` Impact ("the only edit to an existing file's behaviour"), task
  7.10, AC-101/104.
- **Status:** open

### CB-5 [MAJOR] Making the fleet the landing screen breaks three existing E2E specs
- **Source:** `web/tests/e2e/overview-scroll.spec.ts:44-45`, `web/tests/e2e/navigation.spec.ts:24-33`,
  `web/tests/e2e/screenshots.spec.ts:47-52` — all navigate to `/` and assert the projects table.
- **Failure scenario:** the suite fails in three specs for reasons unrelated to the fleet, and the
  `overview-scroll` regression guard — which exists to catch a silent layout bug and documents that
  scripted scrolling is not proof — dies in its `beforeEach` rather than failing loudly.
- **Plan location:** task 7.10; group 9 adds new E2E tasks but no migration task.
- **Status:** open

### CB-6 [MAJOR] "The same ownership check as every other write into a project tree" names a mechanism that does not exist
- **Source:** `lib/set_orch/deploy_ledger.py:207-236` — `decide()` returns False for any existing
  file the ledger never recorded, and models whole-file copy provenance, not a merge into a
  hand-authored file. The only existing writer into a project's settings is `bin/set-deploy-hooks:57`
  with the additive merge at `:236-300`, which performs **no** ownership check.
- **Failure scenario:** the implementer of 6.5 either routes through the ledger — and the install
  button silently does nothing for every project that already has a settings file — or writes
  directly, which is an unguarded write into a consumer tree, and with the obvious merge replaces the
  project's hook arrays wholesale. That incident is documented at `set-deploy-hooks:236-244`.
- **Plan location:** tasks 6.5, 6.6; `design.md` §5.4.
- **Status:** open

### CB-7 [MAJOR] Every property the plan attributes to "the messaging bus" is contradicted by the only bus in this repository, and the plan never says the bus is external
- **Source:** `mcp-server/set_mcp_server.py:498-539` — `send_message` addresses
  `member@hostname[/change-id]`, shells out to a control-chat script, and returns a fixed
  `{"status": "queued", "delivery": "next sync cycle (~15s)"}`; `:462-471` resolves to the **first**
  project holding a control worktree regardless of recipient; `:542` reads the same one. Measured:
  **0 of 39** registered projects have one, so both tools currently error. The second in-tree path,
  `lib/set_orch/api/_sentinel_orch.py:129-145`, appends to a per-project inbox and returns a fixed
  `"sent"`. Neither carries a session id, a seat, a woken-session report or a hold/expiry outcome.
  `grep -rni "seat\|waiter"` over `lib/`, `bin/`, `mcp-server/` returns nothing.
- **Failure scenario:** implemented against the framework's own bus, the address degrades to a member
  name, the delivery report becomes a constant string, and AC-43 ("never broadcast to its room") is
  unsatisfiable. Because the artifacts never name the external bus, an implementer reading only the
  change will build against the in-repo one.
- **Plan location:** `proposal.md` Why; tasks 4.1–4.5, 6.3; `design.md` §3.
- **Status:** open — **this is the largest gap the review found.** The whole `agent-fleet-instruct`
  capability rests on a component the change never identifies.

### CB-8 [MAJOR] The framework's own short-lived `claude -p` subprocesses become tiles, reported as waiting
- **Source:** `lib/set_orch/subprocess_utils.py:302-327` and 27 `run_claude_logged(` call sites
  across `lib/set_orch/` (planner, verifier, digest, auditor, builder, engine, issue paths, gates);
  `lib/set_orch/chat.py:110-145` spawns `claude -p --resume` with the project as cwd.
- **Failure scenario:** during any orchestration run each gate/review call is a live process whose
  cwd is the project or a worktree — exactly what task 2.1 enumerates, and the plan scopes out only a
  session's own `Task` children. Each gets a tile with a "not instructable" input, and when one
  finishes its last log entry is an assistant message with no outstanding tool call, so AC-26 reports
  **waiting** and AC-83 surfaces it as an agent needing a person.
- **Plan location:** tasks 2.1, 3.2, AC-26, AC-83; `proposal.md` out-of-scope.
- **Status:** open

### CB-9 [MAJOR] `useWebSocket` cannot carry terminal traffic — it JSON-parses every frame, drops what does not parse, and cannot send
- **Source:** `web/src/hooks/useWebSocket.ts:25` (URL hard-wired), `:33-40` (`JSON.parse` in a
  try/catch whose catch is a comment), `:3-6` (closed union of orchestration event names); the hook
  returns `{ connected }` only.
- **Failure scenario:** task 8.1 is sized on "the WebSocket hook is reused as it is". Wired to it,
  every raw terminal frame fails to parse, is swallowed silently, and the terminal renders nothing
  with no console error — while keystrokes have no route back at all.
- **Plan location:** `proposal.md` Impact; task 8.1, AC-70/71.
- **Status:** open

### CB-10 [MINOR] Task 2.2 re-implements an existing Layer-1 function whose non-git answer contradicts AC-14
- **Source:** `lib/set_orch/paths.py:46-83` `resolve_project_name()` already resolves through
  `git rev-parse --show-toplevel` + `--git-common-dir`, and returns the literal `"_global"` outside a
  repository. Its docstring names two further copies; `lib/loop/state.sh:284` is a third.
- **Failure scenario:** reusing it collapses every non-repository agent into one `_global` tile,
  contradicting AC-14; writing a fourth copy lets the fleet's project identity drift from the one the
  rest of the runtime keys its directories by.
- **Status:** open

### CB-11 [MINOR] Task 2.6 duplicates the existing capability detector
- **Source:** `lib/audit/check-claude-config.sh:4-60` and its siblings, driven by `bin/set-audit:28`,
  already answer "what is wired in" from files present and already emit JSON.
- **Failure scenario:** two independent answers to the same question, in two languages, which will
  disagree the first time either changes. AC-20 wants the capability set as data; the existing list is
  fixed and in bash, so nothing is shared.
- **Status:** open

### CB-12 [MINOR] The existing session endpoints are scoped to the registry and to orchestration state, so the fleet's own agents cannot reach them
- **Source:** `lib/set_orch/api/sessions.py:566-620` resolves via `_resolve_project` then enumerates
  worktrees from orchestration state; `:624-660` 404s outside that closed set.
- **Failure scenario:** an agent the fleet discovers in a worktree absent from orchestration state, or
  in a project absent from the registry (AC-6), has no reachable session endpoint. If task 7.12 wires
  "open the log" to the existing endpoint, those tiles show an empty log while the fleet lists them as
  live. The parsing is reusable; the endpoints are not.
- **Status:** open

### CB-13 [MINOR] Task 5.7's refusal is app-wide, and a second resume path exists outside `fleet/terminal.py`
- **Source:** `lib/set_orch/chat.py:110-118` appends `--resume <id>` with no check that a process is
  bound to that session; reached from `chat.py:397-460`, guarded only by an in-process status flag.
- **Failure scenario:** today it resumes only ids it created whose process has exited, so it does not
  bite — but the fleet is what makes those sessions visible and resumable, and nothing extends the
  refusal to this path. Any future path resuming an id sourced elsewhere reintroduces the fork
  measured at design §6.1.
- **Status:** open

### CB-14 [MINOR] The watcher budget is stated per agent, while the existing pool already costs one instance per registered project
- **Source:** `lib/set_orch/watcher.py:316-354` starts one watcher per registry entry with no archived
  filter. Measured: the core service holds **39** inotify instances, one per registered project.
- **Failure scenario:** AC-38 is written as "when the number of running agents doubles, the watcher
  count does not increase", which a fleet holding zero watchers satisfies trivially while the
  pre-existing per-project pool keeps growing with the registry the fleet now renders. Where the
  per-user instance limit is smaller, allocation fails and the library falls back to polling
  (`watcher.py:168-172`) — the reassuring-zero case task 3.7 itself warns about, arriving from the old
  pool rather than from the fleet.
- **Status:** open

### CB-15 [MINOR] A terminal that starts an agent must resolve a model through the repo-wide contract, and an unknown role raises
- **Source:** `lib/set_orch/model_config.py:260-298` (`resolve_model(role)` raises on an unknown role;
  roles enumerated at `:46-70`), `lib/set_orch/chat.py:94-108` (the contract: every invocation passes
  `--model` explicitly, resume included), `tests/unit/test_model_touch_point_coverage.py:1-45` (a scan
  asserting no hard-coded model names under `lib/set_orch/`, with an exemption list a new
  `fleet/terminal.py` is not on).
- **Failure scenario:** task 5.1 records no model decision. Spawning bare ships an unattributable
  agent; hard-coding fails the coverage test; calling `resolve_model` raises until a role is added to
  the table — which the active `model-config-unified` change owns, making this a cross-change coupling.
- **Status:** open

### CB-16 [MINOR] A global `/api/fleet/...` family can be shadowed by the existing `/api/{project}/...` wildcards
- **Source:** 80+ routes of the form `/api/{project}/<literal>` across `lib/set_orch/api/*.py`,
  registered in `api/__init__.py:38-49` before any appended router; `helpers.py:68-76` raises
  `404 Project not found`.
- **Failure scenario:** `/api/fleet/sessions`, `/api/fleet/processes` or `/api/fleet/state` are matched
  by the earlier wildcard with `project="fleet"` and 404. The plan names no endpoint paths, so this is
  a constraint on the implementation rather than a defect in the plan — listed because "no existing
  route is modified" and "no interaction with existing routes" are not the same claim.
- **Status:** open

## Code branch — what it checked and found correct

1. `lib/set_orch/fleet/` does not exist and nothing claims the name — zero hits for `fleet` across
   `lib/`, `web/src/`, `bin/`. No collision on the module or on the new page component.
2. Packaging admits the new subpackage without edits (`pyproject.toml:72-76`, `include = ["set_orch*"]`).
3. `psutil` is a declared dependency (`pyproject.toml:27`) — though `lib/set_orch/process.py:20`
   imports it inside a try/except with a `/proc` fallback, so code treats it as optional.
4. Design §1's claim about existing process discovery is accurate — `api/actions.py:467-489` matches
   project paths **inside command lines**, so it is indeed blind to interactive sessions.
5. Design §2's claim about the existing session listing is accurate — `api/sessions.py:358-384` opens
   every file to classify it. Not reusable at 497-file scale.
6. Session-log location logic already exists and agrees with the plan's model
   (`gate_verdict.py:59-74`, `api/helpers.py:63-65`), keyed per working directory, hence per worktree.
7. The `tool_use`/`tool_result` pairing the plan defines as "working" matches the shape the repo
   already parses (`api/activity_detail.py:195-200`, `:277-330`).
8. No pty anywhere in the tree — the terminal is genuinely new work.
9. No terminal emulator in the frontend — the new-dependency claim is correct.
10. Voice reuse is sound: the component takes only callbacks, the key fetch is cached module-level so
    N tiles cost one request, and the endpoint 404s when unconfigured — task 7.6's "absent rather than
    failing" holds.
11. Router composition supports a new module cleanly (`api/__init__.py:37-49`, `server.py:136-141`).
12. No test pins the route inventory or the app's route table across 257 unit files and 17 web unit
    files, so adding routes breaks no unit test.
13. The registry is global and single-file, as the union assumes; 39 entries, all paths existing.
14. Layer placement is defensible — Layer 1 already knows about processes, session logs and inboxes,
    with no project-type knowledge, and no task puts web knowledge into core.
15. No file-level collision with the other active changes; the only shared file is the API include list.
16. The existing battle view is a visualisation of orchestration changes, not a prior fleet view.
17. The sentinel inbox is a distinct mechanism, not a duplicate of instruct — addressed per project by
    file, with no session addressing.
18. Sub-agent turns do not currently pollute a session log on this machine — zero files carry the
    sidechain marker — so excluding sub-agents does not today break the tail-based state rule.
19. Worktree listing with per-worktree branch already exists (`api/helpers.py:220-252`).

## Code branch — what it could not check

- **The external messaging bus itself.** Seats, waiters, the stop-hook and the four-way answer do not
  exist in this repository and the artifacts never name the tool. That measurement belongs on a
  machine that has it installed. *(This is CB-7 seen from the other side.)*
- **Whether a fleet-started agent can be detached from the service cgroup** — measured that it
  currently cannot; whether to change the unit is D-1.
- **The build products under `web/dist/`** — all frontend findings are against source, not against
  what the server currently hands out.
- **The design's log-tail timings** — one machine, one day; task 1.4 already schedules a re-measure.
- **Whether the plan's project-tile count is actually unreadable** — the counts were measured
  (39 projects, 19 archived, 15 live agents) but no screen exists to look at.

---

## Rules branch — findings

Checked against `CLAUDE.md` and `.claude/rules/*.md`. Did not read the source; that is the other
branch's territory.

### RB-1 [MAJOR] Four of the five new Python modules have no logging task, though logging is mandatory
- **Rule:** `.claude/rules/code-quality.md` — "Every new Python module MUST include logging"; "NEVER
  silently swallow errors".
- **Location:** modules created at tasks 2.1, 3.1, 4.1, 5.1 and 6.1. Measured sweep for
  `logg(er|ing)|log level|INFO|DEBUG|WARNING`: exactly **one** task provides for it — 5.6, and only
  for the terminal's process lifecycle.
- **Why it matters:** the plan is built almost entirely out of fallback and degrade paths — bus
  absent (4.4), log unreadable (AC-28), record stale (3.8), session undeterminable (4.6), watcher
  table exhausted (3.7), heuristic binding (2.3) — each precisely the WARNING-level anomaly the rule
  exists for, and each silent. There is also a live trap: the change's own non-persistence requirement
  forbids writing session content "to a log file", and no artifact states the reconciliation the
  project already uses ("log the shape, not the content"), so an implementer can honour one rule by
  breaking the other.
- **Status:** open

### RB-2 [MAJOR] The fourth delivery outcome is implemented in CORE, dropped at the API, and absent from the surface
- **Rule:** `.claude/rules/evidence-discipline.md` — a marker that is true of a narrower subject still
  lies; the false-value class.
- **Location:** CORE carries four (tasks 4.2, 4.5, 9.2). Then task 6.3 still says "the **three-way**
  delivery outcome" while carrying the `…-every-outcome-and-an-outcome-can-expire` tag; task 7.7 says
  "distinguishing **the three**"; `specs/agent-fleet-surface/spec.md` enumerates three and contains
  **zero** occurrences of `held`/`laps`/`expir`, as does every 7.x and 8.x task; `proposal.md` says
  "the three delivery outcomes"; `design.md`'s §3 heading still reads "three outcomes, because there
  are three" while its own body says "A four-way report, not three".
- **Why it matters:** the instruct spec says the lapse "must be carried through to wherever the first
  outcome was shown" — that place is the tile, which has no requirement for it. As written the screen
  ships with three outcomes, so a held message renders as one of them, which AC-49 explicitly forbids.
- **Status:** open

### RB-3 [MAJOR] Two scenarios report a surviving, bus-instructable agent as "no longer reachable"
- **Rule:** `.claude/rules/evidence-discipline.md` — the false-absence class.
- **Location:** `specs/agent-fleet-terminal/spec.md:135-136` and `:146-149` state that the agent is
  **not** thereby unreachable and that "only the terminal column changes to no" — then `:161` and
  `:166` report it "no longer reachable" / "unreachable". AC-76 and AC-77 copy the scenario text.
  Task 5.5 says the opposite and is correct.
- **Why it matters:** the scenarios and ACs are the checkable artifacts; the task is not. A verifier
  ticking AC-76/77 signs off a screen that labels a live agent unreachable after every restart — the
  exact false absence the proposal's opening measurement describes, reintroduced by this change, and
  archived as the durable contract.
- **Status:** **RESOLVED** by D-1. The scenarios were corrected in the opposite direction: after a
  restart the agent is still running and instructable, and the terminal alone is gone.

### RB-4 [MAJOR] Ten one-machine measurements sit undated in requirement text that archives permanently, and one is already false
- **Rule:** `.claude/rules/openspec-artifacts.md` — artifacts must not contain metrics tied to a single
  deployment; `evidence-discipline.md` — a debt figure is a measurement with a timestamp.
- **Location:** `specs/agent-fleet-state/spec.md:167-168` states the per-user inotify instance limit as
  128 with 126 in use. **Measured 2026-08-17 evening: the limit is 512 on this machine and an instance
  allocates successfully** — the ceiling was raised after the morning's research, so the sentence was
  true at breakfast and false by evening. Nine others carry no date either (log counts and timings,
  4-of-12, 3-of-12, 4-of-9, 4-of-20, 8 projects, 5 worktrees, 21 minutes). Verified: no date appears
  anywhere in any spec file.
- **Why it matters:** `design.md` carries the caveat that makes these honest — "evidence for a
  *direction*, not constants to build against" — but the design is not what archives. The rationale
  prose is part of the requirement text, so these land in `openspec/specs/` stripped of the caveat,
  where a later reader takes a raised sysctl for a kernel fact. The fix is to date-stamp each figure
  in place, not to delete it.
- **Status:** open

### RB-5 [MAJOR] A requirement still authorises attaching a terminal to a session "adopted by resuming it"
- **Rule:** `evidence-discipline.md` — the unmeasured state is not the optimistic one; prefer renaming
  to rescoping.
- **Location:** `specs/agent-fleet-terminal/spec.md:15-20` still reads "started itself … **or to a
  session it has adopted by resuming it** into such a process", against the sibling requirement at
  `:75-79` forbidding exactly that, and task 1.3.
- **Why it matters:** every agent this screen lists is a live session, so the clause can never fire —
  yet it reads as authorised behaviour, and the archived spec is read requirement by requirement
  without design §6.1's refutation attached. The user's decision was to pursue adoption by **another**
  route, which is why the requirement must not name the one route measured to corrupt a running
  conversation.
- **Status:** open

### RB-6 [MAJOR] A waiting agent in a project scrolled out of the left column is hidden with nothing marking it
- **Rule:** `.claude/rules/ui-quality.md` — "Compacting must never hide a failure… anything hidden that
  is wrong must be marked **where the reader is standing**."
- **Location:** `specs/agent-fleet-surface/spec.md:19` — projects are "a scrollable column". Measured:
  `scroll|off-screen|fold|out of view|overflow` appears exactly once in the whole surface spec and all
  of `tasks.md` — that line. Hiding is covered at the project-tile and enlarged-tile levels, not at the
  fleet level.
- **Why it matters:** this is the landing screen and the registry holds 39 entries. A waiting agent in
  project 24 sits below the fold with no marker at the top — the reader arrives, sees calm, and the
  screen reproduces the false absence one level up from the one it fixes.
- **Status:** open — D-2, direction recorded, choice not settled.

### RB-7 [MINOR] The header claims every task carries a layer marker; 18 of 72 carry none
- **Rule:** `code-quality.md`, `openspec-artifacts.md` (mark core vs module); `evidence-discipline.md`
  (the name is a second copy of the content).
- **Location:** `tasks.md:14-15` claims "every task says CORE / API / WEB". Measured across all 72:
  7 inline-marked, 47 covered by a group heading, **18 unmarked** — 1.2, 1.4, 1.6, all of 9.1–9.14,
  and 10.1.
- **Why it matters:** group 9 needs it most, mixing CORE pytest work, WEB Playwright work and a manual
  look. An apply agent that reads the header claim as true stops checking.
- **Status:** open

### RB-8 [MINOR] AC-64 and AC-66 have preconditions that can no longer occur
- **Rule:** `evidence-discipline.md` — a dead test looks exactly like a passing one.
- **Location:** AC-64's WHEN ("measurement shows a running session can be resumed…") was refuted by
  task 1.1; AC-66's WHEN ("the measurement has not been made") is false now that 1.1 is `[x]`.
- **Why it matters:** two of 106 acceptance checkboxes are either ticked vacuously or block on an
  unfalsifiable condition. AC-65 is the only live member of the trio.
- **Status:** open

### RB-9 [MINOR] The same "4 of 20" figure is attributed to two different pairs of sources
- **Rule:** `evidence-discipline.md` — a claim and its evidence travel together.
- **Location:** `proposal.md:27-28` attributes it to the process-only and registry-only views;
  `specs/agent-fleet-inventory/spec.md:67-68` attributes it to the project registry and the messaging
  registry.
- **Why it matters:** one is a mis-attribution and no reader can tell which, because neither records
  the command. It is the load-bearing number for decision §5.3 and is not among the three counts task
  1.4 re-measures.
- **Status:** open

## Rules branch — what it checked and found correct

**Confidentiality — clean on every sweep.** All 39 registry names cross-checked against all six
artifacts individually: zero hits. Zero absolute local paths, zero email addresses, zero URLs. A
frequency sweep of every capitalised token found no product, client, brand or person name. No domain
instance data. The change actively strengthens the persistence boundary: two requirements forbid
writing session-derived content to disk, cache, log file or this repository, with
diagnostics-name-shape-only scenarios (AC-21, AC-22, AC-72, AC-73).

**Delta-parser conventions.** `openspec validate --strict` valid. The parser-truncation trap is
avoided — all five specs place scope blocks *before* `## ADDED Requirements`, and this was proven
rather than assumed: the CLI reports 36 deltas, matching the 36 requirement headers exactly, not 0.
All 106 scenarios use four hashtags; every requirement has at least one; all use SHALL language;
every spec has both scope blocks populated with cross-references to the sibling that owns each
exclusion.

**Traceability, both directions, mechanically.** 36 tags vs 36 requirement slugs — zero dangling,
zero uncovered. 106 scenario tags vs 106 scenario slugs — zero unmatched either way. AC numbering
1–106 with no duplicates. All 72 tasks carry a tag; all 106 AC items carry both.

**ADDED vs MODIFIED.** The landing-screen change is the only MODIFIED candidate; the proposal's own
recorded search was re-run rather than accepted, then broadened — no existing requirement owns the
application root, so ADDED-only is correct. The empty `## Modified Capabilities` block parses as no
delta, which is the intent, and its comment records the refuted search pattern rather than only the
conclusion. Nothing elsewhere silently alters existing behaviour; no existing spec mentions waiters.

**Layer marking and architecture.** All 72 tasks measured individually (result is RB-7). Layer 1
abstractness holds throughout, and the plan refuses a violation explicitly twice. The capability set
is data, not a fixed list. One OpenSpec root, no module-level directory. No file under `.claude/`, so
nothing new needs to be deployable, and nothing is written into a carrier `openspec update` rewrites.

**Evidence discipline carried into the plan's own tasks**, checked one by one: the stash-check with
the untracked-restore caveat and re-grep (9.8); the baseline check with a detached worktree,
`PYTHONPATH` at three source roots and the session-end leak assertion (9.9); negative-half assertions
where a positive-only test would pass on a broken build (9.6, 9.11, 9.13, 9.14); the
measurement-inside-its-own-corpus class carried into 1.4, 4.6, 9.14; the exhausted-meter class into
3.7; the harness-has-powers-the-user-lacks class into 9.5 and made normative in the terminal spec; the
absent-vs-empty-key class into 3.3. Tasks 1.1 and 1.2 are `[x]` and both carry their evidence, so the
markers are earned. The one negative result is written up as a finding rather than buried, and both
decisions taken against the exploration's leaning are named with who settled each.

**UI quality.** Compaction-hides-failure honoured at the agent-panel and project-tile levels; the
enlarged-tile mode keeps every other agent as a state-carrying row rather than hiding them; "look at
it" is an actual task (9.10); the pre-answer state distinguishes "still looking" from "genuinely
nothing"; density is treated as a decision. The third level is RB-6.

**Cross-cutting checklist on the app's route file.** Additive; the overview keeps a route and a
navigation entry (AC-104 asserts every prior behaviour); no competing edit in any other change or
worktree; the stale navigation spec is named as debt rather than silently inherited or rewritten.
*(CB-4 and CB-5 qualify this: the additivity claim holds for the file, not for the call sites.)*

**Rules found not applicable by their own scoping:** the GUI rules (scoped to `gui/**`), the design
bridge (self-disables with no design files present — though note the filename collision: this change's
`design.md` is the OpenSpec technical design, not a token sheet), release safety, sentinel autonomy,
readme updates.

## Rules branch — what it could not check

- **Whether the quoted measurements are accurate** — only that they are undated, and that one is
  currently false. Whether the ceiling was 128 when written and has since been raised, or the reading
  was wrong, is exactly the ambiguity a date removes. *(Resolved after the review: it was raised the
  same day — see RB-4.)*
- **Whether design §6.1's commands were actually run as recorded** — re-running them starts and
  resumes live sessions, so §6.1 is accepted on its recorded evidence rather than reproduced.
- **Whether the planned modules and routes collide with existing source** — deliberately left to the
  code branch. *(It found CB-2, CB-4, CB-10, CB-16 there.)*
- **Exact fidelity of the archive merge** — inferred from the CLI's JSON that rationale prose travels
  into the archived spec; not confirmed by performing one.
- **Whether the 18 unmarked tasks would land in the right layer in practice** — marker presence was
  measured, not the correctness of the layer an implementer would infer.

---

## Closing

Both branches ran and both produced findings, so neither excused the other. Neither manufactured a
finding: the code branch states four areas it could not check and the rules branch five, and both
list what they examined and found correct, itemised rather than summarised.

The two branches found disjoint defect classes, which is the reason the mechanism requires two. The
only overlap is the terminal's restart behaviour, and they approached it from opposite ends — the
rules branch found the spec contradicting itself, the code branch found the systemd unit contradicting
both. That pair is also the clearest single argument for the split: neither branch could have found
the other's half.
