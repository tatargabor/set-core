# Design — FleetView

The exploration behind `proposal.md`. Everything here rests on measurements taken on one live
machine; the numbers are quoted as evidence for a *direction*, not as constants to build against.

---

## 1. What an agent is, and why identity is the hard part

```
   ┌─────────────┐        ┌──────────────────┐        ┌─────────────────┐
   │   process   │        │  messaging bus   │        │   session log   │
   │             │        │    registry      │        │                 │
   │ pid, cwd,   │◀──────▶│ seat = agent#id  │◀──────▶│ turns, tools,   │
   │ start time  │  owner │ session id, focus │ session│ timestamps      │
   └─────────────┘        └──────────────────┘        └─────────────────┘
         │                         │                          │
         │  "is it alive?"         │  "who is it,             │  "what is it
         │  "which project?"       │   how do I reach it?"    │   doing now?"
         └─────────────────────────┴──────────────────────────┘
                                   ▼
                              one agent tile
```

Three facts about this triangle decide the design, and all three were measured:

**The process alone cannot name the project.** An interactive session's command line is just the
binary and a flag — the project is only in its working directory. The existing process-tree
discovery matches project paths *inside command lines*, which is correct for orchestrator children
and structurally blind to editor sessions. New discovery reads `cwd`.

**The bus alone cannot see every agent.** In one measurement, 12 live sessions, 9 with a registry
seat. The three without were in projects where the bus is not installed. They must still appear —
they are running work — so discovery is a union, and the tile states which sources knew about it.

**Guessing the link is worse than admitting ignorance.** The obvious heuristic — *the newest log
file in the project's directory belongs to this process* — measured **4 correct of 9**. Every
correct answer came from a project running a single session; every failure from the project running
six. It fails exactly where the screen is worth having, and its failure direction is the expensive
one: not "unknown", but confidently *another agent's log*. So a heuristic pairing is allowed, and
must be **labelled as a guess on the tile**.

---

## 2. State: derived from the log, never from a heartbeat

| what the tile says | how it is determined |
|---|---|
| in a tool, `<name>`, for `<duration>` | a `tool_use` in the log's tail with no matching `tool_result` |
| turn ended | last entry is an assistant message, no outstanding tool call |
| **waiting for a person, for `<what>`** | the runtime's own session record — *not* the log *(added 2026-08-17)* |
| still for `<duration>` | log file mtime |
| unknown | anything else — **never rendered as "idle"** |

The third row is the addition, and it is the one the log cannot supply. An agent stopped at a prompt
looks, in its log, exactly like an agent that finished its turn: nothing outstanding, nothing
appended. Measured — a live session's record went from idle to `waiting` with the thing it waited
for named, within seconds, while its log said nothing new. The row also carries the trap that comes
with it: the same record's timestamps have been measured days stale, so the value is used only when
the record is fresh, and a stale record yields unknown rather than a comfortable answer.

Also measured, and it is the reason the second row was renamed: "turn ended — waiting" used one word
for two states that need opposite responses. A finished turn wants nothing; an agent at a prompt
wants a person, now.

The last row is the rule that matters. A state the framework cannot determine is a gap, and *a gap
is not a zero*: rendering it as idle would put a calm word next to an agent that may be stuck.

**A heartbeat is a proxy, and it was measured failing.** The bus registry's "last seen" is written
when a hook fires or a bus command runs — not when the agent works. It reported an agent silent for
21 minutes whose log had been appended to inside the same minute. "Last moved" comes from the log's
mtime, always.

### Cost

Measured on the largest session directory on the machine: **497 log files, 955 MB total**.
`stat` across all of them: **0 ms**. Reading the tail 64 KB of the largest: **0.1 ms**. Full parse
of a 1.5 MB file: **4 ms** — fine once, not 497 times.

So: **the list view uses `stat` + `tail` only**; a full parse happens when a log is opened. The
existing session-listing path opens every file in the directory to classify it; that approach is
not reusable at this scale.

---

## 3. Instruction: four outcomes, and one of them has a clock

A session running in someone else's terminal cannot be typed into. Injecting keystrokes into a
foreign terminal is refused by the kernel on current systems (`dev.tty.legacy_tiocsti = 0`), and
that is a boundary, not an obstacle to route around.

So the instruction goes on the messaging bus. Its own documented behaviour splits into three cases —
and a fourth was measured later, which is why the heading counts four:

```
  agent WORKING  →  a stop-hook prevents ending the turn with unread addressed mail
                    ⇒ arrives when the current turn ends
  agent IDLE, waiter running  →  the waiter starts a new turn
                    ⇒ arrives now
  agent IDLE, no waiter       →  nothing starts a turn
                    ⇒ sits unread until a human types into that session
```

**A fourth case exists, it was measured, and it is the one a surface would get wrong.** *(added
2026-08-17)* The runtime carries its own cross-session channel — each session's record names a
`messagingSocketPath`, and a peer can address it by name. Sending into a live foreign session over
that channel produced neither of the three outcomes above:

```
  sender's permission-mode class ≠ recipient's
        →  HELD: not delivered to the agent at all; the recipient's *human* is
           prompted to Deny or Deliver, and the recipient's record flips
           idle → status "waiting", waitingFor "permission prompt"
        →  and if that human does not answer, the hold EXPIRES and the message
           is dropped — the sender is told, but only later
```

Measured twice, on two sessions started for the purpose. Both were held; both expired unanswered.
The recipient's setting `crossSessionInbound` governs it and takes `refuse` / `hold` / `accept`
(read out of the runtime binary), with `hold` the behaviour observed. ⚠ Setting it to `accept` in
the *project's* settings file did not change the outcome in the one attempt made; whether a
user-scope setting would is **not established** — do not build on either answer.

Two consequences for this design, and the second is the sharper one:

- **A four-way report, not three.** "Held pending the recipient's approval" is neither delivered nor
  sitting unread: something *did* happen at the far end — a human was interrupted — and the
  instruction still may never arrive.
- **A held message is not a durable state.** It expires on its own. So an outcome shown on a tile is
  a claim about a moment, and a surface that renders it once and leaves it there will be asserting
  a delivery that has since evaporated. This is the same false-value class as the rest of this
  screen, arriving through the one path that looked like a success.

Measured: **4 of 12** live sessions had a live waiter of their own. A uniform "sent" would be
misleading in two thirds of cases, and misleading in the direction that makes someone wait for an
answer that is not coming.

The report is not inferred: the bus's send call returns which seats it actually woke. The tile
shows that answer.

The same measurement found **~30 orphaned waiter processes** — waiters whose session had died.
They neither wake anything nor clean themselves up. **Settled by the user 2026-08-17: they belong in
this change**, as a requirement under `agent-fleet-instruct` — shown next to the missing-waiter
remedy, removable only one named process at a time, through the same ownership check as the install.
They sit there rather than in a cleanup screen because the offer to *install* a waiter is exactly the
moment someone is adding to the pile.

Its fail direction is asymmetric, and the design follows that rather than the count: leaving an
orphan costs a process table entry, while killing a live waiter silently removes the thing that would
have delivered someone's next instruction. So every uncertainty resolves toward not removing, and
there is no bulk-remove at all.

⚠ A note on how that number was obtained, because it is the more useful half. The first count said
5 of 12 — too optimistic — because the counting script's own command line contained the pattern it
was searching for, so it matched itself and credited a session with a waiter it did not have. The
*measurement was inside the corpus it measured*. Any check built for this feature that greps
process lists must resolve each match to an identity rather than counting lines.

---

## 4. Layering

Layer 1 (`lib/set_orch/`) may know about **processes, session logs, and a message bus** — all three
are framework-level facts, true of any project type. It must not know what kind of project an agent
is working in, and nothing here needs it to.

The bus is an **optional dependency**, and its absence has a defined behaviour rather than an
error: agents are still discovered from processes and still show their state; only the input line
is disabled, with the reason on the tile. This is the same posture the framework already takes
toward a project that declares nothing.

---

## 5. Decisions — settled 2026-08-17

All eight are decided; the tables are kept so a later reader sees what was chosen *and what was
rejected*. **Who settled which is recorded per item, because it is the thing a later reader
cannot re-derive:** §5.1, §5.2, §5.4 and §5.8 were put to the user and answered by them; §5.3,
§5.5, §5.6 and §5.7 were adopted from the measurement without asking, on the ground that the
number in each one leaves no second option — each says so, with its number, so the shortcut is
visible and reversible rather than silent.

Two went **against** the leaning recorded during the exploration, and those two are the ones
worth reading: §5.1 and §5.2.

### 5.1 Where the screen lives — DECIDED: a route, and it is the landing screen

| option | consequence |
|---|---|
| a route in the existing dashboard | reuses voice input, WebSocket, tokens, log parsing |
| a standalone page | duplicates all four |
| **a route, and it replaces the current landing screen** ← chosen | strongest fix for the false-absence measurement |

**Decided:** a route in the existing app — *and* it becomes the landing screen. The leaning left
the second half open; the user closed it toward the measurement. The reason is the one in
`proposal.md`: the current landing screen reported "Stopped, 24 days ago" about a project holding
six working agents at that moment. Leaving that screen in front means the change fixes the false
absence everywhere except the place a reader arrives at first.

**What this obliges, and it is not free.** The landing screen is the one surface that must be
correct before anything is selected, so the empty and degraded states stop being edge cases: no
project registry, no messaging bus, no live agent, and a first paint that happens before discovery
has finished. A screen that renders "no agents" while it is still looking is the same false absence
in a new place — so the first paint says *looking*, never *none*.

### 5.2 Terminal now or later — DECIDED: together, in this change

| option | consequence |
|---|---|
| a second change | first screen usable far sooner; message-based input meanwhile |
| **together with the first** ← chosen | one coherent story, much later delivery |

**Decided:** together. This reverses the leaning, and the honest consequence is that the change is
now roughly twice the work and lands much later.

**It also pulls an untested assumption onto the critical path, which §6 records and which nothing
here may paper over.** The kernel boundary in §3 does not move: a session the framework did not
start cannot be typed into. So a terminal is only ever available for sessions **the surface itself
started**, and the fleet splits into two populations:

| population | seeing | instructing | terminal |
|---|---|---|---|
| started from the surface | yes | yes | **yes** |
| started elsewhere (an editor window, by hand) | yes | over the bus | **no** — see below |

~~Whether an existing session can be *adopted* into a framework-owned terminal by resuming it was
**never measured**.~~ **Measured 2026-08-17 — see §6.1. Resume-based adoption is refuted**, and not
because it errors: it returns a correct-looking answer while silently forking the running session
into a second branch. So the third column stays `no` for every session the surface did not start.

**What the user decided once that answer was in** *(2026-08-17, after the measurement)*: the
terminal **stays in this change at its planned size** — it is not narrowed to match the refutation —
and the adoption of foreign sessions is pursued **by another route**, to be measured before anything
depends on it. Two candidates exist and neither is established: the runtime's own cross-session
channel (§3, which reaches a foreign session but is gated by the recipient's human), and a
`--remote-control` mode the CLI offers. Both share the limitation that they must be enabled where
the session *starts*, so neither is yet known to reach a session already running.

Until one of them is measured, every foreign tile keeps the bus input, with the reason stated on the
tile rather than a control that silently does nothing.

### 5.3 What populates the project list — DECIDED: the union

| option | consequence |
|---|---|
| **union of all three sources** ← chosen | nothing that is running is missing |
| project registry only | measured: would hide the projects of 8 discovered agents |
| only projects with a live agent | a project goes missing the moment its agent exits |

**Decided** (adopted from the measurement, not asked): union, with each tile stating which sources
knew about it. The number decides it — 8 projects held a discovered agent while absent from the
project registry, so the registry-only list would hide running work on a screen whose entire
purpose is to stop hiding running work.

### 5.4 Missing waiter — DECIDED: flag it, and offer the install

| option | consequence |
|---|---|
| **flag, and offer a one-click install** ← chosen | the user decides; pairs with cleaning orphaned waiters |
| flag only | the common case stays broken and merely well-labelled |
| install automatically | the framework rewrites settings in projects it does not own |

**Decided** (by the user): flag and offer. Automatic installation would edit another project's
configuration without being asked — the same instinct the deploy-safety work spent a whole track
constraining. The offer is an action the reader takes, so it is subject to the same ownership check
every other write into a project tree goes through; it is not a special case because it is small.

### 5.5 Phase: guessed or declared — DECIDED: declared *(second round)*

| option | consequence |
|---|---|
| **declared; no icon where undeclared** ← chosen | honest, and needs an agreement with projects |
| guessed, marked as a guess | an icon that is wrong when it matters most |
| guessed, unmarked | a confident wrong label |

**Decided** (adopted from the measurement, not asked): declared. Measured, in a session that spent its whole length on specification work,
the obvious signal matched **zero** times. A path-based rule would also carry project shape into the
abstract layer. The *role* — directing or executing — is a different matter: it is measured from the
process tree, so it may have an icon.

### 5.6 How lineage is shown — DECIDED: an edge and a reference *(second round)*

| option | consequence |
|---|---|
| **an edge on the tile plus a reference to the parent** ← chosen | survives any density; no layout dependency |
| grouping children under their parent | readable, but overrides ordering by state |
| a separate tree view | a whole screen for a rare question |

**Decided** (adopted from the measurement, not asked): edge and reference. Measured, 1 of 12 agents was a child — too rare today to reorder
the grid around. Worth reopening if orchestrator-spawned agents are brought into this screen too.

### 5.7 Worktrees — DECIDED: one project tile *(second round)*

| option | consequence |
|---|---|
| **one project tile, branch shown on the agent** ← chosen | matches what a worktree is |
| a project tile per worktree | measured: would split one project into five |
| an expandable project tile | more mechanism for a distinction that is already on the agent |

**Decided** (adopted from the measurement, not asked): one tile. A worktree is where work happens, not another project. This decision is a
**correction**: the first round's screens showed a worktree as a separate project.

### 5.8 What "open the log" shows — DECIDED: the raw conversation

| option | consequence |
|---|---|
| **the raw conversation** ← chosen | answers "what is being said in there" |
| the existing activity timeline | answers "where the time went" — a different question |
| both, as tabs | more surface, and a default still has to be picked |

**Decided** (by the user): the raw conversation. The timeline already exists and can be added as a
tab later without disturbing this; the reverse — shipping the timeline first — would answer a
question nobody opened the tile to ask.

---

## 6. What this design does not know

- **More than one machine.** The bus can relay between machines; process inspection cannot. A
  remote agent could be listed from the registry, but its state could not be measured the same way.
  Single-machine as designed.
- **Platforms other than Linux.** Discovery as measured reads `/proc`. A portable process library
  is already a dependency, but this was not measured elsewhere.
- ~~**Whether an existing session can be adopted** into a framework-owned terminal via resume.~~
  **MEASURED 2026-08-17 — the answer is no, and the way it says no is the finding.** See §6.1.

### 6.1 Adoption by resume — measured, and it fails in the reassuring direction

The unknown §5.2 put on the critical path. Run on two sessions started for the purpose; no session
belonging to anyone else was touched.

**What was run.** A holder process was left running with the session open, and a second process
resumed the *same* session id while it ran:

```
holder :  claude -p --input-format stream-json --output-format stream-json   (stdin held open)
adopter:  claude -p --resume <session-id> "What is the codeword?"
```

**What came back.** Everything a caller would read as success:

| observation | value |
|---|---|
| adopter exit / `is_error` | `0` / `false` |
| history visible to the adopter | intact — it answered with the codeword the holder had been given |
| session id | **the same one**, not a new one |
| session log | **the same file**, 7 → 16 lines |
| holder afterwards | still running, and asked what was last said to it, it named **its own** previous message |
| log structure | one parent with **two children**, **two leaves**, 2 seconds apart |

**So resume does not adopt a running session; it clones its history into a second, divergent
branch** while the original keeps running, unreachable, and nothing anywhere reports that this
happened. There is no lock, no refusal, and no warning. The only tell is in the log's shape, after
the fact.

The direction is what closes the question. A failure that errored would be a limitation; this one
returns a correct-looking answer to the person who asked, while quietly splitting the conversation
the other agent is still having. Building the terminal on it would have produced a feature that
demonstrates perfectly and corrupts under exactly the condition it exists for — two agents in one
project, which is when this screen is worth having at all.

**And the hazard is wider than the feature that provoked it.** Any `--resume` on a live session does
this, not only one made in the name of adoption. Sampled on this machine, **15 of the 60 most
recently modified session logs (25%) already carry branches**, one of them with 11 leaves. So the
surface's obligation is not merely to skip an adoption feature: it must **refuse to offer resume on
a session it can see is running**, because the control looks harmless and its damage is invisible.

### 6.2 Where a started agent lives — decided by the user 2026-08-17, after the review

The adversarial review found that task 5.5's promise was false as the system stands: the dashboard
unit runs with `KillMode=control-group`, and every existing spawn uses `start_new_session=True`,
which changes the process group and **not** the cgroup. So an agent started from the surface joins
the service's cgroup and dies with it — including on the automatic restart after any crash.

**Decided: the agent-owning process is separated from the web service.** One service serves the UI
and the API; another owns agent lifecycle; the two talk to each other. This is not a new pattern
here — a per-project supervisor daemon already exists with its own entry point, owning the
orchestrator subprocess, monitoring it, restarting it and carrying its own inbox and status. The
split extends that shape rather than inventing one, and it also closes a defect already on record:
restarting the dashboard kills the sentinel subprocess.

**The split alone does not deliver the property, and the design must not pretend it does.** It moves
the boundary rather than removing it: when the *agent-owning* service restarts — crash, upgrade,
`Restart=always` — it kills its own agents' cgroup by exactly the same mechanism. Two services means
two places an agent can die from.

So the agent is additionally started in **its own transient scope**. Measured: a scope started this
way lands at `app.slice/<name>.scope`, a **sibling** of the service rather than a child, so it
survives a restart of whichever service started it. It also gives task 5.4's "stopping is deliberate"
a mechanism instead of a convention — the agent becomes a named unit that can be stopped by name and
enumerated after a restart, which is what reattachment needs to even be attempted.

**What this does *not* fix — and the first version of this paragraph was wrong, measured 2026-08-18.**
It said: "the split rescues the *agent*; the terminal column still turns to no." Half of that is
false, and it fails in the reassuring direction. Two probes, isolating the two killers:

| what the agent is attached to | who dies | scope afterwards | agent |
|---|---|---|---|
| the owner's pty | the pty holder | **inactive** | **dead** |
| nothing (no pty) | the process that started it | active | **alive** |

A transient scope protects against a **cgroup kill** — a service restart taking its whole control
group with it. It does not and cannot protect against the agent's **terminal disappearing**: when
the pty master closes, the slave returns EOF and errors on write, and any process reading its own
tty exits. The scope then goes inactive because its last process left. So for a pty-attached agent
the split rescues nothing when the *owner* dies; the agent dies with its terminal.

**The correct statement, and it makes the owner's stability load-bearing rather than convenient:**

- The agent **survives a restart of the web service** — a different unit, a different cgroup, and
  it holds no pty. That is what the scope buys, and it is exactly the property CB-1 asked for.
- The agent **does not survive its own owner's death**, because the owner holds the pty its tty is.
  **The pty holder's lifetime is the agent's lifetime**, not merely the terminal's.

This is why the owner is thin, and the reason is stronger than the one the user's phrasing implied:
an owner that never needs updating is not protecting terminal *uptime*, it is protecting the agents
themselves. There is no arrangement of this mechanism that gives both a terminal and survival of the
terminal-holder — an agent with no pty survives and cannot be typed into; an agent on a pty can be
typed into and dies with it. Any future "detachable" answer just moves the pty into a different
long-lived holder and inherits the same rule.

**A second finding, from trying to drive the terminal from outside.** The pty master file descriptor
cannot be reacquired from another process: `/proc/<pid>/fd/<n>` for a pty master points at
`/dev/ptmx`, and opening that **allocates a new pty pair** rather than returning the existing one.
Measured — a keystroke written that way never reached the session, whose menu selection did not
move. This settles §5.5 rather than leaving it open: an agent whose owning process is gone is
**unreachable**, not reattachable, because the only handle to its terminal died with the owner. A
service restart therefore cannot promise reattachment; it can only report the truth.

**Two properties the user named on 2026-08-18, and both sharpen the decision rather than change it.**

*"A fixed service that exists only for this and never needs updating."* Correct, and the reason is
worth stating because it decides how the service is written, not just that it exists. The transient
scope already saves the **agent** from a restart; what it cannot save is the **terminal**, because
the pty master dies with whoever holds it and cannot be reacquired (measured above). So the owner's
uptime is exactly the terminal's uptime — and an owner that never needs updating is an owner that
never needs restarting. That property is not free: it is bought by keeping the service **thin**.
It holds ptys, relays bytes, and starts and stops named scopes. Everything that changes — discovery,
state, the API, the screen — stays in the web service, which may then be restarted as often as
development requires. **A line of business logic added to the owner is a future terminal outage**,
and that is the standard any change to it must be held to.

*"Then we start and resume."* This closes the case §6.2 above calls unreachable, and the order is
the whole of it. After the owner dies, the agent is alive in its own scope and its terminal is gone
for good. The transcript, however, survives — so the recovery is not reattachment but **replacement**:
resume the session into a fresh pty under a new owner. Two things make it work and one makes it fail:

1. **Stop the orphaned scope first, by name.** It is a named unit precisely so this is possible —
   `systemctl --user stop <name>.scope`, verified 2026-08-18 on a probe scope.
2. **Then resume.** A resumed *dead* session is the ordinary, supported use of resume.
3. **Resuming before stopping reproduces §6.1's fork** — two live sessions appending to one
   transcript, neither aware of the other, nothing reporting it. The measured hazard is not resume
   itself; it is resume against something still running. So the surface must refuse to offer resume
   while the old scope is up, rather than trusting the operator to do it in order.

This is what makes CB-1's remedy honest: the framework does not promise to reattach, it offers to
**stop and resume**, and says which of the two it is doing.

#### Holding a terminal is not neutral — MEASURED 2026-08-18, and it added the only behaviour the owner has

The split above says the owner *holds* ptys, as though holding were a passive act. It is not, and
the measurement is what turned a design word into a required mechanism.

A pty's buffer is small, and a writer blocks when it fills. Probed directly: a child writing to its
own tty while nobody read the master stopped after **17 408 bytes** of the 4 MB it was asked to
write, and a **single** drain of the master let it advance exactly **4 096 bytes** further before
stopping again.

So an owner that holds a master without reading it does not fail — it **freezes the agent**, after
roughly one screenful, and the frozen agent is indistinguishable from a thinking one on every
surface this change builds. The failure direction is the reassuring one twice over: the start
succeeds, the scope is active, the pid is real, and the screen has nothing to report.

Verified end to end against the mechanism rather than the API, by disabling the drain and rerunning
the same probe through the socket:

    with the drain     the child wrote 400 000 bytes and exited cleanly
    drain disabled     the child wrote 0 and blocked; it had to be killed

Two consequences bind the owner, and neither loosens its thinness requirement:

- **The drain is a precondition, not a feature.** It is the one piece of real behaviour permitted
  in the owner, because without it every other guarantee in §6.2 describes a frozen process.
- **What is drained goes into a bounded in-memory tail and nowhere else.** Not to disk, not to a
  log. The conversation already has a durable home in the session log, and a second one here would
  be both a persistence boundary violation and the kind of state that makes a service unrestartable.
  A tail that has lost its head **says so** — a partial stream silently read as the whole one is the
  false-absence class.

---

### 6.3 The bus — MEASURED 2026-08-18, and it settles which channel is the contract

Tasks 1.4, 1.5 and 1.6. Every figure below was taken on this machine on **2026-08-18 between
10:36 and 11:05 CEST**; each is re-runnable from the commands in the change's `measurements`
appendix. Two sessions were started for the purpose, in scratch directories; **no session
belonging to anyone else was sent anything.**

**Coverage — the decisive number.** Live agent processes were enumerated from `/proc` by
`comm == "claude"`, resolved to identity rather than counted by a pattern:

| source | sees | of 21 live sessions |
|---|---|---|
| runtime cross-session channel (`/run/user/1000/cc-socks/<pid>.sock`) | **21** | **100 %** |
| framework bus (`set-agent-comm` registry seat with a live owner) | **11** | **52 %** |

A naive substring match over command lines returned **31 additional false positives** — all of them
shell snapshots whose path contains the word, none of them agents. The identity rule in §1 holds.

**The runtime's address carries a verified identity, and the name does not.** A held message names
its sender as `uds:/run/user/1000/cc-socks/505440.sock **[verified pid 505440]** (peer claims
name: set-core-68)`. The runtime verifies the **pid** from the socket and marks the **name** as a
claim. This is the §1 pairing problem — *guessing the link is worse than admitting ignorance*,
measured at 4 correct of 9 — solved at the source: the process and the session are joined by the
socket's own name, with no heuristic. The framework bus offers nothing comparable; it addresses
`member@hostname`.

**The delivery report is real, not a constant.** An unresolvable recipient returns
`{"success": false, "message": "No agent named '…' is reachable."}`. The framework bus returns a
fixed `{"status": "queued"}` for every send, including into projects where nothing is listening.

**⚠ But the sender cannot tell delivered from held, and this corrects §3.** Two sends were made
from this session (permission class `bypass`): one to a peer in the same class, one to a peer in
`auto`. Both returned **the identical shape** — `success: true` with a `msg_id`. The first was
delivered and answered in ~20 s; the second was **held**, and the hold appeared only on the
*recipient's* screen as a Deny/Deliver prompt. §3 said "the bus's send call returns which seats it
actually woke"; measured, it does not. The send call reports **resolution**, not delivery. So a
tile that renders the send call's answer as an outcome would assert a delivery it has not observed
— the same false-value class this screen exists to avoid, arriving through the one path that
looked like a success.

**The true outcome does reach the sender — asynchronously, and this is what the capability must
listen for.** Measured in the same run: the send returned `success: true` at ≈10:47:40, and at
≈10:52:20 — **roughly four to five minutes later, unprompted** — the runtime delivered a notice to
this session: *"Your message to another session was held for the recipient user's approval
(recipient: `uds:/run/user/1000/cc-socks/2632885.sock`). Not delivered to that session's Claude
yet; its user must approve first."* The pid in that socket is exactly the recipient's. So the
outcome is **available and identity-bearing**, just not synchronous: it arrives on a separate
channel, minutes late, keyed by the recipient's verified socket rather than by the `msg_id` the
send call returned. `agent-fleet-instruct` therefore has two distinct facts to model — *accepted
for delivery* (synchronous, from the send call) and *what actually happened* (asynchronous, later)
— and a tile must show the first as **pending**, never as delivered.

**Expiry is a SECOND, distinct notice — measured 2026-08-18, and the two must not be collapsed.**
The hold was left deliberately unanswered. The sender received two separate notices on the same
channel:

| # | wall clock (observed) | text |
|---|---|---|
| send | ≈10:47:40 | `{"success": true, "msg_id": …}` |
| 1 | observed by 10:52:32 | *"…was **held** for the recipient user's approval… its user must approve first"* |
| 2 | observed by 10:53:55 | *"…was **not approved before expiry**… Not delivered to that session's Claude"* |

So the outcome sequence for one instruction is **three states, not two** — accepted → held →
expired — and the middle one is not terminal. A surface that renders the first notice it receives
and stops will show *held* for a message that is already dead. **Expiry landed roughly six minutes
after the send** (bounded by observation: not before ~5.5 min, not after 6.75 min); treat that as
an order of magnitude on one machine, not a constant, and read the terminal state from notice 2.

⚠ **What was NOT established, deliberately.** Whether the Deny/Deliver prompt disappears from the
recipient's screen when the message expires is **unknown**. The recipient's pty scrollback still
contained the prompt text afterwards — but that is exactly the redraw-buffer proxy described
below, so it is not evidence either way, and the tempting conclusion (*"the recipient is still
being offered a message the sender was told is dead"*) is unproven. The only facts here are the
two sender-side notices.

⚠ **And a note on how the expiry was nearly mis-measured.** A watcher was pointed at the last 3 KB
of the recipient's pty log, waiting for the Deny/Deliver prompt to disappear. It fired instantly
and reported a change that had not happened: a TUI redraws continuously, so the tail window is a
*redraw buffer*, not the screen's state, and the prompt drifts in and out of any fixed-size window.
This is the proxy-instead-of-the-thing class again — the scrollback tail is a proxy for what is on
screen. The reliable signal was the sender-side notice, which is a fact rather than a rendering.

**Adoption — §5.2's remaining route, and the answer is again no.** The channel **reaches** a
session that is already running: input is delivered, an idle peer wakes, and a reply comes back as
a message. It does **not attach a terminal**: there is no output stream, no pty, and no way to
observe the peer's screen — the only return path is a message the peer chooses to send. Remote
Control is *not measured*: the account has used it (`hasUsedRemoteControl: true`) but nothing is
connected here, so `ListAgents` showed no remote row. Not measured is not negative — do not build
on either answer.

**Two live causes for the invisible-agent case (task 2.8), both caught by accident.** The first
session started for this measurement did not appear in the channel's listing while it sat at its
**start-up trust prompt** — alive, and invisible. Once past it, it was still invisible, for a
second reason: it had inherited `CLAUDE_CODE_CHILD_SESSION` from this session's environment and
announced *"Transcript saving is off"*. Only after stripping every `CLAUDE_*` variable from the
child's environment did it register. Both are alive, both are invisible to the runtime source, and
neither is exotic — the second is what any framework-spawned session inherits by default.

**Orphans are a property of every source, not of the framework's bus.** Measured the same minute:
**58 of 79** sockets in `cc-socks/` belong to dead pids; **59 of 77** framework registry seats have
a dead owner; **17 of 26** `sac wait` waiter processes have no live agent ancestor. The waiter
requirement §5.4 settled for the framework bus therefore generalises — whatever channel is chosen,
its roster needs the live-process join, and a directory listing is not a roster.

**Updated counts for §1 and §3, which were taken on one day on one machine:**

| figure | as written | measured 2026-08-18 |
|---|---|---|
| live sessions | 12 | **21** |
| with a registry seat | 9 | **11** (52 %) |
| with a live waiter of their own | 4 of 12 | **6 of 21** |
| orphaned waiters | ~30 | **17** |

One session owns **four** waiters at once, which no requirement anticipated: a per-session waiter
count is not one, and a "missing waiter" check must count, not test presence.

### 6.4 What a project has wired in — MEASURED 2026-08-18, and the record task 2.9 prefers barely exists

Prompted by a question the walking skeleton provoked the moment it listed twelve projects:
*do these all have the framework installed, and is it current?* Measured across the twelve
projects that had a live agent.

**Ten of twelve carry no framework rule at all.** Two do:

| | rules present | content equal to today's template | covered by the install ledger | ledger date |
|---|---|---|---|---|
| the flagship consumer | 16 | **3** | **4** | 2026-07-24 (25 days) |
| a second project | 22 | **22** | **0** | no ledger |

**The consequence for task 2.9, and it inverts the task's own assumption.** 2.9 says to take the
capability report from the install record *where one exists*, and to fall back to inferring from
files *only where no record exists*, marking such an entry inferred. Measured: a record exists for
**1 project of 12**, and inside that project it covers **4 of its 16 rule files**. So the fallback
is not the exception — it is the answer for eleven projects out of twelve, and for three quarters
of the files in the twelfth. The surface must therefore treat *inferred* as the normal case and
make it legible, not as a rare footnote.

**And `.claude/` is not the signal.** Every one of the twelve has that directory, because every
project a person opens an agent in has one. Counting it would have reported 12 of 12 installed —
a false value of exactly the kind this screen exists to avoid, and the first thing measured here.
The `opsx` command count is no better: it spread 5 → 13 across the twelve *including set-core's
own 12*, because those files are generated by the OpenSpec CLI in each project rather than
deployed by the framework. A capability report has to name what the framework actually installs.

**What the ledger does answer, where it exists, is worth the ledger.** For the flagship's 11
ledgered paths the recorded install hash separates the two causes of a difference that otherwise
look identical: **8 untouched and matching, 3 edited by the project and correctly left alone, 0
where the framework's own template had moved**, plus **11 tombstones honoured**. That is the
provenance discipline working exactly as designed. The problem is not the mechanism; it is
coverage — the ledger shipped after most of these files were deployed, so it is answering for
about a tenth of what is on disk. **Un-ledgered is not a synonym for stale, and the surface must
not render it as one:** for those files the framework simply cannot tell a project's own edit from
its own drift, and *cannot tell* is the honest report.

### 6.6 Three things the surface CANNOT claim — MEASURED 2026-08-19 while building the slice

Each of these was found by implementing a task whose wording assumed a mechanism that is not
there. They are recorded together because they share a shape: **the task named a source, the
source exists, and it does not answer the question.**

**A record's timestamp is the age of the STATE, not of the observation.** Task 3.8 asks for a
freshness check before believing the runtime's declared status, since those stamps have been
measured days stale. Measured on 25 live records: `updatedAt` equals `statusUpdatedAt` in **22 of
22** that carry both, so the record is written only when the status *changes*. An agent waiting
three hours honestly carries a three-hour stamp, and an age threshold would discard the true
positives first — it would have discarded the only real `waiting` on this machine, whose stamp was
9.5 hours old. Cross-checking against the log's mtime fails in the other direction: **22 of 22**
logs had moved since their status stamp, so it rejects everything.

What works is composing the sources rather than ranking them. The log decides *working* from
*not-working*, structurally. The record may refine a *quiet* state into *waiting*, because only it
knows. A record claiming *waiting* while a call is outstanding is contradicted, the measurement
wins, and the disagreement is carried rather than dropped — that is the staleness that actually
fires here (one record still said `busy` while its log showed no outstanding call).

**Lineage is not in the process tree.** Task 2.5 asks for the parent by walking ancestry to the
first agent ancestor. The walk is correct and answers almost nothing: **0 of 23** live agents had
an agent ancestor. More decisively, an agent started from this screen has the OWNER — a plain
python process — as its parent, with systemd above it, so no walk will ever find *which agent asked
for it*. That relation exists only during the act of starting, so it is recorded during it. The two
answers are kept apart on the wire (`source: recorded | ancestry`) because they answer different
questions and can disagree, and the recorded one is a **claim the framework did not verify**.

**A stop's return value is not a state.** Task 5.9 already had `stop()` escalate to SIGKILL, and it
never ran: `_await_gone` accepted "not active", and a unit enters `deactivating` the instant a stop
is requested. So `stop()` returned `gone=True` in **0.0 seconds** while the agent ran on for four
minutes. The consequence for this design is not the fix but what it invalidates — **a re-read is
only a guard if it asks a different question than the one that can be wrong.** Task 5.11's
verification re-read `still.active`, which is precisely what the stop path had mis-answered, so the
guard against the §6.1 silent fork was open for exactly the case it exists for. "Gone" now asks
about the processes: a cgroup holding a pid is not gone, whatever systemd calls the unit.

### 6.5 A THIRD source of state — an agent that reads the others, requested by the user 2026-08-18

**Deferred on purpose, and the user said so: this matters once the base functions work.** Recorded
here rather than in a notebook because the shape has to be settled before anyone builds it, and
because it is easy to build in a way that destroys what the rest of this screen is for.

**What was asked.** To know from the terminals *what is running, what is waiting and what is
finished* — by having an **external agent read their output**. Because that reader knows which
agent was given which task, it can say what state each one is in.

**Why it does not duplicate anything here.** This screen already has two sources, and this is a
third with different properties:

| source | how it answers | can it be wrong? |
|---|---|---|
| **measured** — an outstanding tool call, the log's mtime | structurally, from the log | no; it can only be *undetermined* |
| **declared** — the agent states a phase (3.4) or a blockage (3.5) | the agent says so | only if the agent lies about itself |
| **interpreted** ← this | a reader infers from output plus the assigned task | **yes, silently, and plausibly** |

**The four constraints it must obey, each of which is a defect class this repository has already
paid for:**

1. **An interpretation is a guess, and must be labelled one wherever it is shown** — the same
   discipline §1 imposes on a heuristic log binding. It may add a state, never replace a measured
   one, and never silence an `unknown`. A reader that turns "I could not determine this" into
   "finished" has produced exactly the false value this screen exists to prevent, in the one place
   that looks most like insight.
2. **Its fail direction must be chosen deliberately, and it is not symmetric.** Reporting *waiting*
   for an agent that is working costs a glance; reporting *finished* for an agent that is stuck
   costs the work. So an uncertain interpretation resolves toward *needs a look*, never toward
   done.
3. **A reading agent's verdict is not evidence.** Measured in `.claude/rules/evidence-discipline.md`:
   an unflagged subprocess asked to create a file replied `Done.` with exit 0 and the file did not
   exist. So a "finished" interpretation is a *claim* that must be checkable against a trace —
   a commit, a completed task in the engine's run state, a green gate — and the surface shows the
   trace next to the claim, or shows that there is none.
4. **It reads conversation content, so the confidentiality boundary binds it hardest.** The
   boundary is persistence, not reading: this reader may consume a consumer project's session and
   must write nothing derived from it — not to a cache, not to a log, not into memory, and not into
   a prompt that is itself recorded somewhere. Its output belongs on screen and nowhere else.

**One measured caution about the input it would read.** The terminal is not available for a foreign
session (task 5.2, and adoption was measured to fail twice — §6.1 and §6.3), so "reading the
terminals" in practice means reading the **session logs**, which every agent has through a recorded
binding. That is a better input anyway: it is structured, it survives the browser, and it carries
the tool calls the reader would otherwise have to parse out of rendered output. What it does *not*
carry is anything a session did outside its own transcript — and a session started as another
session's child writes no transcript at all (§6.3), so the reader will have blind spots that are
invisible to it. It must report coverage, not just conclusions.

**Where it belongs.** Not in `agent-fleet-state`, which is defined as measurement. Its own
capability, so that a reader can tell at a glance which claims on this screen were measured and
which were inferred.

## 7. How this will be proven, when it is built

Two checks decided in advance, because both classes of failure here are the reassuring kind:

**Discovery, against a known truth.** The registry's process-to-session bindings are recorded by
the sessions themselves. A test asserts the discovery result against those bindings and fails on
any *silent* mismatch — the heuristic fallback must be labelled, and a labelled guess is not a
failure while an unlabelled one is.

**Delivery, mutated.** A test that only checks "the send call was made" would pass identically on
all three delivery outcomes, since the call succeeds in every one. The assertion is on the reported
outcome for each case, and the fixture drives the three states apart explicitly.

**The terminal, driven the way a person drives it** *(added with §5.2)*. A test that writes to the
pseudo-terminal's file descriptor and reads the echo proves the plumbing and nothing else — it is
the harness using a power the user does not have. The assertion is that a keystroke entering the
**browser-side terminal component** reaches the agent process and that the agent's output comes
back to the same component. And the negative half matters as much: for a session the framework did
**not** start, the surface must offer no terminal at all, rather than one that opens and swallows
what is typed into it.

Both are written against the *result*, not the *mechanism*: that a route returned a payload and
that a tile rendered are compatible with the answer being wrong. The last check is to open the
screen and look at it.

---

## 8. The work-cycle engine, which lands first and owns half of this screen's data

*(Added 2026-08-18, after the engine's plan was written.)* A sibling change brings the consumer's
proven sectioned work cycle into the framework as a module: an engine that runs a work unit in a
fresh agent context, resolves task groups and their dependencies, hands a run its slice, takes a
schema-constrained verdict, gates it, and records open decisions as durable markers in the task
file. It lands **before** this screen, by an explicit ordering decision — the modern foundation is
lifted first and orchestration is rebuilt on it, never the reverse.

That matters here more than a neighbouring change usually does, because **it owns the answers this
screen was otherwise going to invent.** Five places moved:

| what this screen needs | where it was going to come from | where it comes from now |
|---|---|---|
| what an agent is working towards | nowhere — a field with no source | the engine's recorded run state |
| how far it has got | undefined | completed tasks in the change's task file |
| starting work from the surface | spawning an agent process directly | the engine's one command entry point |
| what a project has wired in | sniffing for files | the module install record, with versions |
| answering a question an agent asked | a message to a session | the deferred-work connector, keyed |
| wiring a missing capability into a project | a bespoke install, on a check that does not exist | the module installer |

**The first row is the one that was actually missing**, and it came from the user rather than from
the engine: an agent needs a stated purpose — why it is running — its name may even *be* that
purpose, and how far it has got must be visible. Measured before writing it down: the phrase
"declared focus" appeared exactly once in this change, in the proposal, as a field to render; the
specs mentioned it only in a prohibition against persisting it, and the task list did not mention it
at all. The screen was going to draw a field with no source, no vocabulary and no notion of
progress. The engine supplies all three.

**Progress is counted in completed tasks, and that is a borrowed answer rather than a fresh one.**
The consumer's own cycle already settled it: a ticked task is real movement, a turn count is only
activity. Conflating them produces a screen that shows a run going round in circles as progress,
which is a false value of the most expensive kind — it is confidence about the one thing the reader
opened the screen to check.

**The third row is a constraint, not a gift.** The engine's contract says any caller starting a unit
— naming the framework's own surface explicitly — uses the same entry point, and that no second
mechanism exists. This change had three tasks describing the surface spawning an agent itself. Left
as written they would have been that second mechanism, and the damage would land here rather than
there: a run started outside the engine is absent from the engine's recorded state, so the screen
would have started something it then could not describe. The resolution costs nothing — the surface
runs *the engine's command* under the pty it owns, which leaves every terminal rule in §5.2 and §6.2
untouched.

**The fifth row exposed a gap neither the adversarial review nor the design had found.** An open
decision is written into the task file and outlives the run that produced it. So the ordinary shape
of a project blocked on a question is: question recorded, no process alive, nothing to show on any
agent tile. An agent-centric screen renders that project as holding zero agents — indistinguishable
from a project with nothing to do, and it is the single project on the screen a person could unblock
in a minute. This is the change's own founding defect, arriving through the state that most needs a
reader, and it required a new requirement rather than an adjustment.

### 8.0 The install surface has no owner, and this screen is where it lands

The module-install capability puts **"rendering the install surface" explicitly out of its own
scope**, while the user's stated intent is that modules are installed into projects *from the web*.
So the mechanism has an owner and the surface does not. This screen is the plausible home and was
already halfway there without noticing:

- Its capability report distinguishes *not connected* from *unknown* on the stated ground that "not
  connected invites wiring it in". An invitation the screen cannot accept is decoration.
- It already carried an install action — one task, for one capability — and measured against the
  source, that task rested on an ownership check **that does not exist**: the deploy ledger refuses
  any existing file of unknown provenance, and the only writer into a project's settings performs no
  check at all.
- That task had **no requirement above it**. It was tagged to a requirement about *reporting* that an
  agent cannot be instructed, which says nothing about installing anything. An orphan task is how a
  capability gets built to nobody's stated standard.

All three resolve the same way and none of them is new scope: the install belongs to the installer,
the screen asks for it, and the screen shows what came back.

**What the installer's contract obliges the screen to show** is the part worth writing down, because
it is where a surface silently undoes a guarantee. The installer must report every skipped file and
its reason, and must say so when a run changed nothing — a silent skip being, in its own words, the
same class of defect as a silent overwrite. Those are constraints on the *installer's output*. A
screen that runs it and renders "done" has moved the silence one layer up, to where the reader is
actually standing, and it does so in the reassuring direction: the skip is usually the *correct*
behaviour (the project edited that file), so the outcome is good and the screen is lying about it.

**The scope line drawn here, so the next reader does not have to guess.** This change owns the
affordance where a project is *missing* something the screen already reports — install what is not
connected, show what the installer did. It does not own a module catalogue, upgrades, removal, or
per-version management. Those want a surface of their own, and this change is already large.

### 8.1 What happens where the engine is absent

Every one of the five degrades to the posture this change already takes toward a missing bus (§4):
the capability is absent, the absence is *stated*, and nothing is inferred to fill it. No purpose is
shown rather than a guessed one; capability presence falls back to inference and says that it is an
inference; the surface offers no unit-start where there is no engine; an answer has nowhere keyed to
go, so the control is not offered. This screen must render a machine with no engine installed
anywhere, because for a while that is every machine.

### 8.2 The direction of the dependency, and what would make it wrong

This change reads what the engine records; the engine knows nothing about this change. That
direction is a requirement rather than an accident — the same rule the engine sets for itself
against the orchestration core. If a task here ever needs the engine to write something *for the
screen*, that is the signal the boundary has been drawn in the wrong place, and it should be raised
rather than accommodated.

---
