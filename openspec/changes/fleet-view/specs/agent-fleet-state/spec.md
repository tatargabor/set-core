## IN SCOPE
- Deriving what an agent is doing right now from its own session log
- Deriving how long it has been since that agent last moved
- Reporting a state that cannot be determined as unknown
- The cost of doing the above across every agent on the machine

## OUT OF SCOPE
- Explaining where an agent's time went (the existing activity timeline answers that)
- Interpreting, summarising or judging what the agent is working on
- Any state of a project that is not an agent's state (orchestration status is unchanged)

## ADDED Requirements

### Requirement: Activity is read from the session log, never from a heartbeat

The time an agent last moved SHALL be taken from its session log's last write. The framework SHALL
NOT report activity from a registry's last-seen timestamp.

A registry timestamp records when a hook fired or a command ran — not when the agent worked.
Measured on a live machine: the registry reported an agent silent for 21 minutes whose session log
had been appended to inside the same minute. It is a proxy for the thing, and it fails toward calm,
which is the direction that hides a working agent behind a quiet label.

#### Scenario: Last movement comes from the log
- **WHEN** an agent's session log was written to more recently than its registry entry was updated
- **THEN** the reported time-since-movement is measured from the log

#### Scenario: A stale registry does not make an agent look idle
- **WHEN** a registry entry is hours old and the session log is seconds old
- **THEN** the agent is reported as recently active

### Requirement: An outstanding tool call is what "working" means

The framework SHALL derive the current activity from the tail of the session log: a tool invocation
with no matching result outstanding means the agent is in that tool, and the tool's name and elapsed
time SHALL be reported. A last entry that is an assistant message with no outstanding tool call
means the turn has ended.

This distinction is the whole question the surface answers. "In a tool for 19 minutes" and "turn
ended 18 minutes ago" look identical from the outside — one is work in progress, the other is an
agent waiting for a person — and only the log separates them.

#### Scenario: An agent inside a tool
- **WHEN** the log tail holds a tool invocation with no matching result
- **THEN** the state is working, naming that tool and how long it has been outstanding

#### Scenario: An agent that finished its turn
- **WHEN** the last log entry is an assistant message and no tool call is outstanding
- **THEN** the state is waiting

### Requirement: A state that cannot be determined is unknown, never idle

When the framework cannot derive an agent's state — the log is unreadable, absent, or its tail is
inconclusive — it SHALL report the state as unknown, and SHALL NOT report it as idle, finished, or
any other determinate state.

A gap is not a zero. Rendering an undetermined state as idle puts a calm word where the framework
measured nothing, and an agent stuck behind a prompt is exactly the case most likely to produce an
inconclusive tail.

#### Scenario: A session with no log yet
- **WHEN** a live process has no session log written yet
- **THEN** the agent is listed as running with an unknown state

#### Scenario: An unreadable log
- **WHEN** the session log cannot be read
- **THEN** the state is unknown and the reason is reported

#### Scenario: A status field that is absent, not empty
- **WHEN** a source of state omits the status field entirely rather than leaving it blank
- **THEN** the state is unknown, and a test for any particular state SHALL NOT be the thing that
  decides it

A measured instance, found on a headless run: the native session record carries no `status` key at
all for such a run. A reader written as `record.status === "waiting"` then returns false — a
**false negative for an agent that is genuinely waiting for a person**. That is worse than the
record being missing, because a missing record is visibly missing, while a false negative is
indistinguishable from "nothing to do here". Distinguish absence from every determinate value
before comparing against one.

### Requirement: Waiting for a person is a state of its own, and it says what for

The framework SHALL report an agent that is waiting for a person as waiting, distinctly from
working, from having finished a turn, and from unknown, and SHALL carry what it is waiting for where
the source names it. This state MAY be taken from the runtime's own session record rather than from
the log, and where it is, the record's freshness SHALL be checked before the value is believed.

The log cannot answer this question. An agent stopped at a prompt has an ordinary-looking tail — the
turn has not ended and no tool is outstanding — so every rule in this capability that reads the log
classifies it as one of the states it is not. Measured, the runtime's record answers it directly:
sending into a live session flipped its record from idle to waiting with the thing it was waiting
for named alongside, both times, within seconds.

It earns an exception to this capability's own rule against non-log sources because it is a
different source from the one that rule rejects: the heartbeat rejected above is written when a hook
fires, while this is the runtime describing itself. The exception is narrow and comes with the check
attached — the same record's timestamps have been measured stale by days, so freshness is asserted
rather than assumed, and a stale record yields unknown, never a determinate state.

This is the most actionable state on the screen. An agent waiting for a person is the one case where
a reader can act immediately, and it is invisible in every other state model here.

#### Scenario: A waiting agent is reported as waiting
- **WHEN** the runtime's record reports the session as waiting and names what for
- **THEN** the agent is reported as waiting, carrying that reason

#### Scenario: A waiting state is not derived from the log alone
- **WHEN** the log's tail is inconclusive and the record is absent or stale
- **THEN** the state is unknown, not waiting and not idle

#### Scenario: Waiting outranks a quiet log
- **WHEN** an agent's log has not moved for a long time and the record reports it waiting
- **THEN** it is reported as waiting for a person, not as merely still

### Requirement: What an agent is working towards is read from the engine's record, never guessed

Where a project is driven by the work-cycle engine, the framework SHALL take an agent's declared
purpose and its progress from the engine's recorded run state — which change it is running, which
group, and the verdict of the last unit — and SHALL measure progress in completed tasks rather than
in turns or events. A recorded state claiming a run in progress whose process is gone SHALL be
reported as stale, never as running. Where no such record exists, the framework SHALL report no
purpose rather than inferring one.

An agent without a stated purpose cannot be told apart from the agent beside it, which is the
complaint this screen exists to answer: several agents in one project, all of them "busy", none of
them saying what for. The engine already records the answer, and records it where a reader can read
it without running anything — so guessing here would be inventing a field next to a source.

Progress is counted in completed tasks because the alternatives measure the wrong thing. A turn
count and an event count both rise while an agent goes round in circles; a completed task is
movement. The two are not interchangeable, and a screen that shows the first as the second reports
progress that is not happening.

The stale rule is the same one this capability applies to every other borrowed source: a record is
believed only while its subject is alive, and an unbelievable record yields unknown rather than the
comfortable answer it happens to contain.

#### Scenario: An adopted project reports purpose and progress
- **WHEN** an agent runs in a project the engine drives, and the engine has recorded a run
- **THEN** the agent reports what it is working on and how far it has got, from that record

#### Scenario: A stale run is not reported as running
- **WHEN** recorded state claims a run in progress whose process is no longer alive
- **THEN** it is reported as stale, distinguishably from a live run

#### Scenario: No engine, no invented purpose
- **WHEN** a project has no engine record
- **THEN** the agent reports no purpose, and the absence is stated rather than shown as an empty
  label

#### Scenario: Progress is completed work, not activity
- **WHEN** progress is reported
- **THEN** it is derived from completed tasks, and not from a count of turns or events

### Requirement: A phase is reported only where the agent declared one

The framework SHALL report an agent's phase of work only from a declaration made by that agent, and
SHALL NOT infer it from the log's contents, the tools used, or the paths touched. Where no phase is
declared, none is reported, and the surface shows no phase.

Measured in a session that spent its entire length on specification work: the most obvious signal —
a slash command naming the phase, in that session's own log — matched **zero** times, because most
work does not begin with one. A tool distribution says what an agent is doing, not where it stands.
And a path-based rule would put project-shaped knowledge into the abstract layer, which the
architecture forbids and which the next project would contradict by keeping its files elsewhere.

The failure direction decides it: a guessed phase is wrong precisely when the situation is unusual,
and an unusual situation is why someone opened this screen.

#### Scenario: A declared phase is shown
- **WHEN** an agent declares the phase it is in
- **THEN** the surface reports that phase

#### Scenario: An undeclared phase produces no icon
- **WHEN** an agent declares nothing
- **THEN** no phase is reported, and none is inferred from its log

#### Scenario: Role is not a phase
- **WHEN** an agent is known to have spawned another agent
- **THEN** its directing role may be reported, because that relation was measured rather than guessed

### Requirement: A declared blockage is independent of the measured state

Where an agent declares that it cannot proceed, the framework SHALL report that independently of
its measured runtime state, and SHALL NOT show it only alongside any particular state.

The two are orthogonal, not overlapping. A measured "waiting" means the runtime is waiting for
someone at the terminal to type; a declared blockage means the agent has said it cannot go on, and
named what it is blocked on. An agent can be busy **and** blocked at once — working on a detour
while waiting for an answer — and that is exactly the case worth surfacing. Tying the badge to the
waiting state would hide "working, but stuck on an answer for three hours", which the surface is
required to show even on the project tile.

#### Scenario: Blocked while busy
- **WHEN** an agent's measured state is busy and it has declared itself blocked
- **THEN** both are reported, and the blockage is visible

#### Scenario: Waiting is not blockage
- **WHEN** an agent's measured state is waiting and it has declared no blockage
- **THEN** no blockage is reported — it may simply have finished a turn

### Requirement: Watching the fleet costs a bounded number of file watchers

The framework SHALL NOT create a file watcher per agent. The number of watchers it creates for
fleet observation SHALL NOT grow with the number of agents.

Measured on a live machine: the kernel allows 128 inotify instances per user, 126 were in use, and
this repository's own web service held 39 of them in a **single process with a single event loop**.
At saturation the failure is silent and points the wrong way: existing watchers keep working, while
every **newly** armed one falls back to slower polling. So the session that suffers is the one just
opened — the newest agent, which is the one most likely to be watched.

How much a watcher costs is runtime-dependent, so the requirement is stated as a bound rather than
as a mechanism. On one runtime a process opens a single instance regardless of how many directories
it watches; on the one this service uses, each call consumes one. A design that relies on the
cheaper behaviour breaks silently when it runs on the other, and silence is the whole problem here.

#### Scenario: Watchers do not scale with agents
- **WHEN** the number of running agents doubles
- **THEN** the number of watchers the framework holds does not increase

#### Scenario: Log content is read, not watched
- **WHEN** an agent's log is displayed
- **THEN** its content is read on demand rather than by arming a watcher per log

### Requirement: Listing every agent does not read every log in full

Deriving state for the list SHALL read file metadata and a bounded tail of each session log. A full
parse SHALL happen only for a log the caller has opened.

Measured on the largest session directory on one machine — 497 logs, 955 MB in total — metadata
across all of them cost 0 ms and a 64 KB tail of the largest cost 0.1 ms, while a full parse of a
single 1.5 MB log cost 4 ms. Full parsing is affordable once and not 497 times, and a list view
that grows slower as history accumulates stops being opened.

#### Scenario: The list is derived from metadata and tails
- **WHEN** the fleet inventory derives state for every discovered agent
- **THEN** no session log is read in full

#### Scenario: An opened log is parsed fully
- **WHEN** a caller opens one agent's log
- **THEN** that log alone may be parsed in full
