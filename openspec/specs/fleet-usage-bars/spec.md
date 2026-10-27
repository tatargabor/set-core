# Fleet Usage Bars Specification

## Purpose

Owns what the fleet screen draws from that measurement: a mark on the header's own line —
at rest the bars alone, two stripes per window, consumption above and elapsed time below,
coloured by the severity the service itself states. It also owns what the mark must say when
it knows nothing, and what compacting may never hide.

## IN SCOPE

- A mark on the fleet header's own line, at rest carrying BARS ONLY for the accounts that
  answered with figures — no name, no percentage, no sentence
- Two stripes per window — consumption and elapsed time — so "ahead of budget" reads without arithmetic
- Colouring from the upstream severity, and a distinct mark for an unmeasured window
- An icon and a count for every state that has no bar, so compacting the words cannot
  compact away a failure with them
- Saying how old the measurement is, and saying so where the reader is standing
- A detail view, one click away, naming every account and every window

## OUT OF SCOPE

- Attaching consumption to an agent tab or tile: the quota is account-wide and per-seat
  attribution is not measurable here (see the requirement below for the measurement)
- Acting on the number: no throttling, no blocked start, no warning modal
- Cache heat, which is a different measurement on the same screen and keeps its own marks
- The Control Center's window, which keeps its own strip and its own requirements

## Requirements

### Requirement: The strip belongs to the header, because the quota is not a per-agent fact

The fleet screen SHALL draw account usage on its header's own line, and SHALL NOT attach a
consumption mark to an agent tab or tile.

At rest it SHALL carry one mark per account that answered with figures — the bars, preceded by
a short label naming that account — and SHALL make each mark's account recoverable without
navigating away. The accounts by name, and every window including any model-scoped one, SHALL
be reachable in one step from that mark.

The resting form stays compact, but not wordless: several accounts draw the same-shaped pair
of bars, and pairs that cannot be attributed are names the reader must reconstruct from a
tooltip to use at all. Asked for by the user on 2026-08-29 — a word, an icon or a letter
before the bars. The label is the shortest text that distinguishes the accounts: for an email,
the domain's first label (`gmail`, `itline`), because the shared local part distinguishes
nothing; otherwise the name, capped. Full names, percentages and sentences still live only on
the mark's description and in the detail view — the 2026-08-27 compaction
(*"ez nagyon sok helyet elvisz … szovegek nem kellenek"*) survives as everything the label
does not say.

The reason the marks are per account and not per tab is a measurement, not a layout
preference. A per-tab mark would claim that this agent consumed this share, and that claim
cannot be supported: of the 40 most recent session transcripts on this machine, measured
2026-08-27, **4 carried an owning-account identity and 36 did not**, and the stored account
entries carry no account identifier to join on at all. A mark drawn on 4 tabs out of 40 is not
a coverage gap the reader can see — it looks exactly like 36 agents consuming nothing.

#### Scenario: More than one account answered with figures

- **WHEN** the machine holds several usage-capable accounts and more than one answered
- **THEN** the header carries one mark per answering account, each preceded by its short
  label, and each still names the account it stands for in full in its description

#### Scenario: Two accounts that would draw identical bars

- **WHEN** two accounts with different names rest beside each other
- **THEN** their labels differ, so the pairs are attributable without opening anything

#### Scenario: An agent tab is drawn

- **WHEN** the fleet screen renders its agent tabs and tiles
- **THEN** no account-consumption mark appears on any of them

#### Scenario: The reader asks for the detail

- **WHEN** the reader opens the detail from that mark
- **THEN** every account is listed by name with every one of its windows, and the detail does not
  displace the header or the screen below it

### Requirement: Each window draws consumption against elapsed time

For each rolling window the screen SHALL draw two stripes in one bar: consumption above, and how
far the window itself has elapsed below. Both SHALL be drawn from the same measurement's
timestamps rather than from the browser's own clock arithmetic over an absent figure.

The pair is the point. A single consumption bar at 60 % answers nothing on its own — 60 % consumed
one hour into a five-hour window is a problem, and 60 % four hours in is not. Two stripes make
"ahead of budget" a comparison the eye performs, which is the same shape the Control Center's own
strip has used since it shipped.

#### Scenario: Consumption ahead of elapsed time

- **WHEN** an account has consumed a larger share of a window than the share of the window that has
  elapsed
- **THEN** the consumption stripe reads as longer than the elapsed stripe

#### Scenario: Both windows are shown

- **WHEN** an account carries both a 5-hour and a 7-day window
- **THEN** both are drawn on the row, each labelled with the window it stands for

### Requirement: Colour states the reported severity, and one weight means one thing

The screen SHALL colour a window's mark from the severity the measurement reports, and SHALL NOT
compute a band of its own. The colour reserved for a critical window SHALL NOT be used decoratively
anywhere in the strip.

The severity a measurement reports is the severity its source stated, or — for a source that
states none — the band its measurement applied, in the one place that source's specification
defines. The screen cannot tell those apart and does not need to: its rule is the same either
way, take the severity the record carries and never derive one from the percentage. With more
than one source behind one strip, wording on the screen SHALL NOT attribute a band to the
service, because for one of the sources that attribution is not true.

#### Scenario: A window arrives labelled critical

- **WHEN** the measurement reports a window's severity as critical
- **THEN** that window's mark is drawn in the critical colour

#### Scenario: A window arrives labelled normal

- **WHEN** the measurement reports a window's severity as normal
- **THEN** the mark is not drawn in the critical colour, whatever its percentage

#### Scenario: A window banded at measurement

- **WHEN** a window's severity was banded by its own source's measurement rather than stated
  by that source's upstream
- **THEN** the screen colours it by that severity through the same rule as any other window,
  and no wording on the screen names the service as the band's author

### Requirement: An unmeasured window is marked, never drawn as an empty bar

Where the measurement reports a window as unmeasured, or an account as unreachable or unconfigured,
the screen SHALL draw a mark that says so and SHALL NOT draw a bar at zero fill. The three states
SHALL be distinguishable from one another without hovering.

An empty bar is the most confident thing on the screen: it reads as "nothing consumed". It is drawn
in exactly the cases where nothing is known, which inverts the meaning at the moment it matters.

#### Scenario: A reachable account with a null window

- **WHEN** an account answers but one of its windows carries no figure
- **THEN** that window shows the unmeasured mark, and no bar is drawn for it — at rest as a count,
  and in the detail as a mark beside the window it belongs to

#### Scenario: An unreachable account

- **WHEN** an account could not be reached at all
- **THEN** it is reported under its own mark, counted separately from accounts whose windows were
  merely unmeasured, so the two causes cannot be read as one

#### Scenario: No accounts are configured

- **WHEN** the machine holds no usage-capable account
- **THEN** the strip says no account is configured, rather than drawing empty bars

### Requirement: The strip says how old its measurement is

The strip SHALL carry the time of the measurement it is drawing whenever that measurement is older
than one polling interval, and SHALL keep drawing the last good measurement rather than replacing
it with an error when a refresh fails.

A stale screen is readable only if the reader can see how stale. Trading a true-but-old measurement
for no measurement is the worse of the two on a landing screen — the same reasoning the header's
refresh-failed chip already carries.

#### Scenario: The measurement goes stale

- **WHEN** the last measurement is older than one polling interval
- **THEN** the strip states when it was taken

#### Scenario: A refresh fails

- **WHEN** a refresh fails after an earlier measurement succeeded
- **THEN** the earlier figures stay on screen, marked with their age, rather than disappearing

### Requirement: The compact state never hides a failure

A window whose severity is critical SHALL be marked wherever the reader is standing — in the
resting state as much as in the detail — and the same SHALL hold for an account that answered with
no figures and for one that did not answer at all. Each of the three SHALL carry its own mark, so
two different causes are never counted as one.

This is the condition the compacting is allowed under, not a caveat to it. Any layout that hides
something creates a place a broken thing can sit while the screen looks calm, and a tidy header
reporting quiet it has not verified is worse than a crowded one that does not. Words may be
compacted to icons and counts; a failure may not be compacted to nothing.

#### Scenario: A critical window with the detail closed

- **WHEN** the strip is at rest and one account holds a critical window
- **THEN** a mark stating that is visible without opening anything

#### Scenario: Nothing is critical

- **WHEN** no window is critical
- **THEN** no critical mark is shown, in either state

#### Scenario: An account with no figures and one that did not answer

- **WHEN** one account answered with no figures and another did not answer at all
- **THEN** each is counted under its own mark at rest, and the two counts are separate

### Requirement: The header renders whether or not the measurement arrived

The fleet header SHALL render completely when the usage measurement is absent, slow, or failing,
and the usage request SHALL NOT be able to delay or prevent the rest of the screen.

#### Scenario: The usage endpoint does not answer

- **WHEN** the usage request fails or has not returned
- **THEN** the fleet header, its counts and the screen below it render as they do today, and the
  strip states that the measurement is unavailable

### Requirement: The dead are purgeable from where they are counted

Where the strip reports accounts that did not answer, it SHALL offer the purge action for
exactly those accounts. The action SHALL require an explicit confirmation that names the
accounts and states that their stored credentials will be deleted, and after a confirmed
successful purge the strip SHALL refresh rather than wait for its next poll.

The wording SHALL say the accounts did not answer — never that their credentials expired.
Unreachable is also what a network failure looks like, and the strip does not know which
of the two it is looking at; the confirmation is the human decision that stands in for
that missing knowledge.

The action SHALL be present only while at least one account did not answer, and SHALL
draw no more attention than the count it serves: an offering, not a banner.

#### Scenario: Accounts did not answer

- **WHEN** the strip is showing the accounts that did not answer
- **THEN** the purge action is reachable from that line

#### Scenario: Nothing is silent

- **WHEN** every account answered
- **THEN** no purge action is offered anywhere in the strip

#### Scenario: The confirmation

- **WHEN** the purge action is triggered
- **THEN** a confirmation names the accounts and states that their stored credentials
  will be deleted, and nothing is removed until it is accepted

#### Scenario: A confirmed purge succeeds

- **WHEN** a confirmed purge completes successfully
- **THEN** the strip refreshes its measurement rather than waiting for the next poll
