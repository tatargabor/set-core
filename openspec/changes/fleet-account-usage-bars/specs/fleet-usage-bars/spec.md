## IN SCOPE

- A strip in the fleet header carrying one row per configured account
- Two stripes per window — consumption and elapsed time — so "ahead of budget" reads without arithmetic
- Colouring from the upstream severity, and a distinct mark for an unmeasured window
- Saying how old the measurement is, and saying so where the reader is standing
- Keeping a critical account visible when the strip is collapsed

## OUT OF SCOPE

- Attaching consumption to an agent tab or tile: the quota is account-wide and per-seat
  attribution is not measurable here (see the requirement below for the measurement)
- Acting on the number: no throttling, no blocked start, no warning modal
- Cache heat, which is a different measurement on the same screen and keeps its own marks
- The Control Center's window, which keeps its own strip and its own requirements

## ADDED Requirements

### Requirement: The strip belongs to the header, because the quota is not a per-agent fact

The fleet screen SHALL draw account usage in its header, one row per account, and SHALL NOT attach
a consumption mark to an agent tab or tile.

The reason is a measurement, not a layout preference. A per-tab mark would claim that this agent
consumed this share, and that claim cannot be supported: of the 40 most recent session transcripts
on this machine, measured 2026-08-27, **4 carried an owning-account identity and 36 did not**, and
the stored account entries carry no account identifier to join on at all. A mark drawn on 4 tabs
out of 40 is not a coverage gap the reader can see — it looks exactly like 36 agents consuming
nothing.

#### Scenario: More than one account is configured

- **WHEN** the machine holds several usage-capable accounts
- **THEN** the header carries one row per account, each naming the account it stands for

#### Scenario: An agent tab is drawn

- **WHEN** the fleet screen renders its agent tabs and tiles
- **THEN** no account-consumption mark appears on any of them

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

### Requirement: Colour states the upstream severity, and one weight means one thing

The screen SHALL colour a window's mark from the severity the measurement carries, and SHALL NOT
compute a band of its own. The colour reserved for a critical window SHALL NOT be used decoratively
anywhere in the strip.

#### Scenario: A window arrives labelled critical

- **WHEN** the measurement reports a window's severity as critical
- **THEN** that window's mark is drawn in the critical colour

#### Scenario: A window arrives labelled normal

- **WHEN** the measurement reports a window's severity as normal
- **THEN** the mark is not drawn in the critical colour, whatever its percentage

### Requirement: An unmeasured window is marked, never drawn as an empty bar

Where the measurement reports a window as unmeasured, or an account as unreachable or unconfigured,
the screen SHALL draw a mark that says so and SHALL NOT draw a bar at zero fill. The three states
SHALL be distinguishable from one another without hovering.

An empty bar is the most confident thing on the screen: it reads as "nothing consumed". It is drawn
in exactly the cases where nothing is known, which inverts the meaning at the moment it matters.

#### Scenario: A reachable account with a null window

- **WHEN** an account answers but one of its windows carries no figure
- **THEN** that window shows the unmeasured mark, and no bar is drawn for it

#### Scenario: An unreachable account

- **WHEN** an account could not be reached at all
- **THEN** its row says so, distinguishably from an account whose windows were merely unmeasured

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

### Requirement: Collapsing the strip never hides a critical account

Where the strip can be collapsed or reduced, a window whose severity is critical SHALL remain
marked in the collapsed state, at the place the reader is standing.

Any layout that hides something creates a place a broken thing can sit while the screen looks calm.
A tidy header that reports quiet it has not verified is worse than a crowded one that does not.

#### Scenario: The strip is collapsed with a critical account present

- **WHEN** the reader collapses the strip and one account holds a critical window
- **THEN** a mark stating that remains visible in the collapsed strip

#### Scenario: The strip is collapsed with nothing critical

- **WHEN** the reader collapses the strip and no window is critical
- **THEN** no critical mark is shown

### Requirement: The header renders whether or not the measurement arrived

The fleet header SHALL render completely when the usage measurement is absent, slow, or failing,
and the usage request SHALL NOT be able to delay or prevent the rest of the screen.

#### Scenario: The usage endpoint does not answer

- **WHEN** the usage request fails or has not returned
- **THEN** the fleet header, its counts and the screen below it render as they do today, and the
  strip states that the measurement is unavailable
