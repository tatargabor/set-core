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

## 3. Instruction: three outcomes, because there are three

A session running in someone else's terminal cannot be typed into. Injecting keystrokes into a
foreign terminal is refused by the kernel on current systems (`dev.tty.legacy_tiocsti = 0`), and
that is a boundary, not an obstacle to route around.

So the instruction goes on the messaging bus, and the bus's own documented behaviour splits into
three cases:

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

**A second finding, from trying to drive the terminal from outside.** The pty master file descriptor
cannot be reacquired from another process: `/proc/<pid>/fd/<n>` for a pty master points at
`/dev/ptmx`, and opening that **allocates a new pty pair** rather than returning the existing one.
Measured — a keystroke written that way never reached the session, whose menu selection did not
move. This settles §5.5 rather than leaving it open: an agent whose owning process is gone is
**unreachable**, not reattachable, because the only handle to its terminal died with the owner. A
service restart therefore cannot promise reattachment; it can only report the truth.

---

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
