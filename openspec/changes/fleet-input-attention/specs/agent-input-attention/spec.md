## IN SCOPE

- Reading the runtime session record's `status` (`busy` / `shell` / `idle` / `waiting`) and
  `statusUpdatedAt` as a MEASUREMENT of the session's own loop
- Deriving one attention class per agent: working, background-busy, waiting for input,
  stopped at a prompt, or unmeasured
- The duration a session has been waiting for a person with nothing running
- A single declared escalation over that duration — plain, then amber, then red
- Rendering that escalation in the project menu: on the project row, on the group header,
  and on the agent's own state line
- Saying whether a message typed at that session would be acted on now or merely queued

## OUT OF SCOPE

- Deciding whether a quiet session's last turn ASKED for something — that is the model
  judgment layer (`agent-fleet-pm-judgment`) and stays there
- The attention QUEUE, its ordering, and the countdown (`agent-fleet-attention-queue`)
- Any change to how *working* is measured from the session log — the log keeps that job
- Notifying, waking, or writing into a session
- Work awaiting a human with no agent on it (`awaiting`, task 7.14) — a different shape
  on the same row, unchanged here

## ADDED Requirements

### Requirement: The runtime record's status is read as a measurement of the session loop

The framework SHALL read `status` and `statusUpdatedAt` from the runtime's per-session record
and SHALL treat them as a measurement of that session's own loop rather than as a stale
declaration.

This reverses a decision this repository took on 2026-08-18, so the evidence travels with it.
Measured 2026-08-28 on runtime 2.1.251: `statusUpdatedAt` matched the last log entry's own
timestamp in **10 of 10** live sessions carrying a log, while the log's **mtime** was up to
**90 minutes** later than any entry in **2 of those 10** — the log file is rewritten without
new entries, so mtime OVER-reports movement. A live pty probe measured `idle → busy` at
**0.6 s** after a prompt, `busy → shell` when the agent backgrounded a command, and
`shell → busy → idle` at the turn's end, every stamp landing within **0.2 s** of the change.

The record is written when the status CHANGES, so an old stamp on a non-`busy` status is the
true age of that state, never evidence of staleness.

#### Scenario: An idle stamp hours old is the wait's duration

- **WHEN** a session's record says `idle` and `statusUpdatedAt` is two hours old
- **THEN** the agent SHALL be reported as waiting for input for two hours
- **AND** the record SHALL NOT be rejected as stale

#### Scenario: The session log's mtime is not used for the wait duration

- **WHEN** a session's log file mtime is newer than its `statusUpdatedAt` and the log holds no
  entry newer than that stamp
- **THEN** the reported wait duration SHALL come from `statusUpdatedAt`
- **AND** the mtime SHALL NOT shorten it

### Requirement: Four statuses map to four distinct attention classes

The framework SHALL map the record's status to exactly one attention class per agent:
`busy` → **working**, `shell` → **background** (the prompt is free, a background command is
still running), `idle` → **input** (waiting for a person, nothing running), `waiting` →
**prompt** (stopped at a permission prompt or a worker request, with `waitingFor` carried
verbatim when present).

`shell` is kept apart from both neighbours deliberately. Measured in runtime 2.1.251, it is
computed as `base === "idle" && a background bash is running`, so it is the only value that
answers the question this capability exists for: the session is not working, and it is also
not waiting for anybody.

#### Scenario: A backgrounded command is not a person waiting

- **WHEN** a session's record says `shell`
- **THEN** the attention class SHALL be `background`
- **AND** it SHALL NOT be counted or rendered as waiting for input

#### Scenario: A permission prompt names what it is waiting for

- **WHEN** a session's record says `waiting` and carries `waitingFor`
- **THEN** the attention class SHALL be `prompt`
- **AND** the reason SHALL be carried verbatim, uninterpreted

### Requirement: A missing status is unmeasured, never idle

The framework SHALL report the attention class as **unmeasured** when the record is absent, or
present without a `status` key, and SHALL NOT map that absence onto any other class.

Measured 2026-08-28 on runtime 2.1.251, and unchanged since the first measurement on
2026-08-18: a headless run (`entrypoint: sdk-cli`) registers a record with **no `status` key at
all**. Reading absence as `idle` would report a working orchestration agent as a person's
problem — the false-absence direction, and the one a reader acts on by interrupting work that
was fine.

#### Scenario: A headless run is not reported as waiting

- **WHEN** an agent's record carries no `status` key
- **THEN** the attention class SHALL be `unmeasured`
- **AND** no wait duration SHALL be reported for it

### Requirement: A measured question outranks the record

The framework SHALL keep the log-measured `asking` state — an outstanding question tool — when
the record's status disagrees, and SHALL carry the disagreement rather than discarding it.

The record answers *is this loop running*; the log answers *what is it stopped on*. Where both
speak, the one that names a specific outstanding call is the more specific claim.

#### Scenario: An outstanding question tool wins over an idle record

- **WHEN** the log holds an outstanding `AskUserQuestion` and the record says `idle`
- **THEN** the agent's state SHALL remain `asking`
- **AND** the attention class SHALL be `prompt`

#### Scenario: A contradiction is carried

- **WHEN** the record says `idle` while the log holds an outstanding non-question tool call
- **THEN** the measured `working` state SHALL win
- **AND** the payload SHALL name that the record disagreed

### Requirement: The escalation thresholds are declared once and carried to the surface

The framework SHALL declare the input-wait escalation as two thresholds — **15 seconds** to
amber and **180 seconds** to red — and SHALL expose the resolved tone alongside the duration so
that the surface renders a decision it did not re-derive.

A threshold implemented once in Python and once in TypeScript is two thresholds, and they drift
silently: a screen colouring at 20 s while a count colours at 15 s reports two different fleets.

#### Scenario: Below the first threshold nothing is marked

- **WHEN** an agent has been waiting for input for 9 seconds
- **THEN** the tone SHALL be the plain one
- **AND** it SHALL still be reported as waiting for input

#### Scenario: The amber band

- **WHEN** an agent has been waiting for input for 45 seconds
- **THEN** the tone SHALL be amber

#### Scenario: The red band

- **WHEN** an agent has been waiting for input for 4 minutes
- **THEN** the tone SHALL be red

#### Scenario: A background-busy agent never escalates

- **WHEN** an agent's attention class is `background` for 10 minutes
- **THEN** no input-wait tone SHALL be resolved for it

### Requirement: The project menu shows the worst wait it contains

The project row SHALL carry the escalation of the LONGEST-waiting agent in that project, and a
collapsed group header SHALL carry the escalation of the longest-waiting agent in the group.

A screen that hides a four-minute wait behind a collapsed group is the layout failure this
project's UI rule names: compacting must never hide a failure. The maximum is used rather than
an average or the freshest, because one busy agent must not vouch for a project whose others
have stopped.

The ROW carries the escalation, not only a marker inside it — the user's own reading of the
first version on 2026-08-28: *"a projekt kártya háttere lenne színezve, jobban látszik mint az
agent darab és perc"*. A 6 px dot and a two-character age are a small target in a column of
forty rows. The tint stays faint and is carried mostly by a left edge bar, so it does not
compete with the selected row's background — the one piece of state the reader sets by hand —
and only the two loud bands tint at all: a column where every row is coloured has said
nothing.

#### Scenario: A collapsed group carries its worst wait

- **WHEN** a group is collapsed and one agent inside it has been waiting for input for 5 minutes
- **THEN** the group header SHALL carry the red escalation

#### Scenario: One waiting agent is enough, whatever the others are doing

- **WHEN** a project holds two working agents and one that has been waiting 5 minutes
- **THEN** the row SHALL carry the red escalation
- **AND** the working agents SHALL be counted from the attention axis, so a session whose
  loop is running but whose log holds no open call is still counted as working

#### Scenario: A wait with no measured age is amber, never silent

- **WHEN** an agent's class is `input` and the record carried no timestamp
- **THEN** the tone SHALL be amber
- **AND** it SHALL NOT resolve to no tone at all

#### Scenario: The row itself carries the colour, not only its marker

- **WHEN** a project's longest wait is past a threshold
- **THEN** the row's own background and edge SHALL carry that tone
- **AND** a row whose longest wait is below the first threshold SHALL stay untinted

#### Scenario: The project row takes the maximum, not the freshest

- **WHEN** a project holds one agent waiting 4 minutes and one waiting 5 seconds
- **THEN** the project row SHALL carry the red escalation

### Requirement: A wait past fifteen minutes goes cold, not louder

The framework SHALL treat an input wait of **900 seconds or more** as **parked** — counted,
carried, and excluded from the escalation — and the surface SHALL mark it with a distinct cold
shape rather than with amber or red.

The escalation is deliberately NOT monotonic in age, and the reason came from the live screen
rather than from theory. A project whose oldest session has been waiting two hours renders red
forever, so the forty-second wait the reader is actually working with never surfaces — the
user's words on 2026-08-28: *"mindig egy pirosat látnék … és soha nem látnám egyébként a
másikat, amit használok"*.

A two-hour wait and a forty-second wait are not the same fact at two volumes. The first is
abandoned: nobody is standing on it. A mark that shouts for two hours teaches the reader to
stop looking, which is how a screen loses the one signal it exists to carry.

#### Scenario: The abandoned wait does not own the row

- **WHEN** a project holds one agent waiting two hours and one waiting forty seconds
- **THEN** the row's escalation SHALL be the amber of the forty-second wait
- **AND** the two-hour wait SHALL be counted as parked, separately

#### Scenario: A project holding only parked waits is counted, not coloured

- **WHEN** every waiting agent in a project is past the parked threshold
- **THEN** the row SHALL carry no escalation tone
- **AND** the parked count SHALL still be shown, so the wait is not hidden

### Requirement: When a person last wrote here is measured, and it is not the wait

The framework SHALL measure, from the session log, how long ago a PERSON last wrote into each
session, and SHALL carry it as a value distinct from the input wait. A tool result SHALL NOT
count as human input, and an absent answer SHALL mean *not seen in the bounded tail*, never
*never*.

This is the signal that separates *the agent I am working with* from *the one I let go*, and
it is not the same as how long the agent has been waiting. Measured on the live fleet
2026-08-28: 0.2, 9.5 and 129.9 minutes across three sessions whose waits said far less about
which one mattered. It measures typed messages only — opening a session or clicking on it is
not attention, which is exactly the case the user described.

#### Scenario: Tool traffic is not a person

- **WHEN** the log's newest `user` entry is a tool result and the newest human message is an
  hour old
- **THEN** the reported human-input age SHALL be one hour

#### Scenario: No human entry in the tail is unknown, not neglect

- **WHEN** the bounded tail holds no human entry at all
- **THEN** the reported human-input age SHALL be absent
- **AND** it SHALL NOT be rendered as a long silence

### Requirement: Amber means waiting for you, and nothing else

The surface SHALL use amber only for an input wait past the first threshold, and SHALL render
an unmeasured state with a distinct shape rather than with amber.

One visual weight per meaning. Amber currently marks *unknown state*; giving it a second
meaning would make the reader ask which one a mark is, which is the cost the rule exists to
avoid.

#### Scenario: An unmeasured agent is not amber

- **WHEN** an agent's state could not be measured
- **THEN** its marker SHALL be distinguishable from an input-wait marker by shape, not only by
  hue

### Requirement: The surface says whether typing there would be acted on

The agent's state line SHALL say whether a message sent to that session now would be acted on
(the prompt is free) or would be queued behind work already running.

This is the question the reader is actually asking of the project menu — the user's own framing
on 2026-08-28 was that a message written into a working session is *pointless* — and it is
answerable exactly and only from the four-value status.

#### Scenario: A working session says a message would queue

- **WHEN** the attention class is `working` or `background`
- **THEN** the state line SHALL say a message would be queued

#### Scenario: An idle session says a message is acted on now

- **WHEN** the attention class is `input`
- **THEN** the state line SHALL say the session would act on a message now

### Requirement: Nothing measured here is persisted

The framework SHALL NOT write any session's status, wait duration, project name, or excerpt
derived from this measurement to disk, to a log line, or to any committed artifact.

The fleet spans consumer projects whose names and contents are confidential; the boundary is
persistence, not display.

#### Scenario: A log line carries no subject content

- **WHEN** the attention class is computed for an agent in a consumer project
- **THEN** any log line emitted SHALL name counts or shapes only, never the project's own text
