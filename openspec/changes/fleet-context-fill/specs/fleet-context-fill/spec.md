## IN SCOPE
- One context-fill mark per LIVE agent on the fleet header's own line, beside the account quota bars
- Resolving each agent's context window from the model the runtime MEASURED, not the recorded provider
- A distinct unmeasured mark when the window or the token count is unknown
- A cap on how many marks the header draws, with a count for the remainder
- Stating in the mark's description that the token figure is a proxy, and what it is a proxy for

## OUT OF SCOPE
- Account quota, which is a different measurement and keeps `fleet-usage-bars`' own marks
- Cache heat (what a keystroke costs), which keeps its own marks on the same screen
- Acting on the fill: no throttling, no blocked start, no forced compact, no warning modal
- Predicting WHEN an agent will compact — the compact threshold is the runtime's, not this screen's
- The change-list context figures owned by `context-window-metrics`, read from `loop-state.json`
- Any new upstream call, credential, or poller: both inputs are already in the fleet payload

## ADDED Requirements

### Requirement: A fill mark per live agent, on the header's own line

The fleet screen SHALL draw one context-fill mark per LIVE agent on its header's own line, beside
the account usage marks, and each mark SHALL be drawn against that agent's OWN context window.

Per-agent is correct here where it is forbidden for account quota, and the difference is the
measurement rather than a preference. Account quota has no per-seat identity to join on — measured
2026-08-27, 4 of 40 transcripts carried an owning account — so a per-tab quota mark would render 36
agents as consuming nothing. Context is read from the agent's own transcript, so it needs no join
and has no attribution gap.

Drawing every agent against one window would be a false value: the windows differ by more than
four times (200 000, 272 000, 900 000), so a shared denominator reports a healthy GLM session and
an overflowing Astra one as the same figure.

#### Scenario: Several live agents, on different providers

- **WHEN** the fleet holds live agents whose measured models resolve to different windows
- **THEN** the header carries one fill mark per live agent
- **AND** each mark's fill is that agent's tokens over ITS OWN model's window

#### Scenario: No live agents

- **WHEN** no agent is live
- **THEN** the header carries no context-fill mark, and no empty or zero-width bar

### Requirement: The window is resolved from the MEASURED model, never the recorded provider

The window SHALL be resolved from the model the runtime reports for that agent. The recorded
provider SHALL NOT be used to resolve it, and an agent whose provider is unrecorded SHALL still
receive a mark whenever its measured model is known.

Measured on the running dashboard: a live agent carried `provider: {"recorded": false}` while its
measured model was present. Resolving from the record would have left that agent — and every other
unrecorded one — with no bar, which on a screen of bars reads as an agent consuming nothing rather
than as a gap in the record.

#### Scenario: Provider unrecorded, model measured

- **WHEN** an agent's provider is unrecorded and its measured model is known
- **THEN** a fill mark is drawn, resolved from the measured model

#### Scenario: The record and the measurement disagree

- **WHEN** an agent's recorded model and its measured model resolve to different windows
- **THEN** the window from the MEASURED model is used
- **AND** the mark's description states the model it was resolved from

### Requirement: An unknown window is unmeasured, and never a bar

An agent whose window cannot be resolved, whose token figure is missing, or whose token figure
EXCEEDS its resolved window, SHALL be marked unmeasured with the strip's existing `?` form, and
SHALL NOT be drawn as an empty, zero-width or full-width bar.

A context cannot exceed its own window, so a figure larger than the window is evidence that the
WINDOW is wrong — not that the agent is full. Measured 2026-09-08 on a live fleet: 3 of 7 agents
exceeded, every one a million-token session whose recorded model name drops the marker that says
so, and whose true window is not recoverable from the process either. Rendering those as critical
would mark nearly half a fleet for a limit none of them is near.

Absent is not zero. An empty bar is a claim that the agent has consumed nothing, which is the most
confident and least true statement this mark can make; a full bar is the same error in the other
direction. This is the rule `fleet-usage-bars` already applies to a window that answered with no
figure, held here so one screen does not teach two readings.

#### Scenario: The measured model has no known window

- **WHEN** an agent's measured model is not in the window table
- **THEN** the mark is the unmeasured form, not a bar
- **AND** its description names the model that could not be resolved

#### Scenario: The agent carries no token figure

- **WHEN** an agent has no cache record, so no token figure exists
- **THEN** the mark is the unmeasured form, not a bar

#### Scenario: The token figure exceeds the resolved window

- **WHEN** an agent's token figure is larger than the window resolved for its model
- **THEN** the mark is the unmeasured form, and its description says the window is wrong
- **AND** no fill, band or bar is reported for that agent

#### Scenario: The token figure exactly fills the window

- **WHEN** an agent's token figure equals its resolved window
- **THEN** the agent is measured, at a full fill

### Requirement: The token figure is stated as a proxy

The mark's description SHALL state the token count, the window it is measured against, the model
that resolved it, and that the count is a PROXY for context size rather than a context measurement
the runtime published.

The figure is the cache read plus cache creation of the last request. It tracks context closely
enough to be worth drawing and is not the same quantity, and a screen that presents it as an exact
context reading invites a decision the measurement does not support.

#### Scenario: Reading one mark's description

- **WHEN** a reader inspects a drawn fill mark
- **THEN** the description carries the token count, the window, and the resolved model
- **AND** it states that the count is a proxy for context size

### Requirement: The cap may not hide a fuller agent

The header SHALL draw at most a fixed number of fill marks and SHALL show a count of the agents
not drawn. The marks drawn SHALL be the FULLEST ones, so that every agent hidden by the cap is
emptier than every agent shown.

Every layout that hides something creates a place a filling agent can sit while the header looks
calm. Ordering by fullness is what makes the cap safe: the reader can conclude from the visible
marks alone that nothing worse is hidden behind the count.

#### Scenario: More live agents than the cap

- **WHEN** more live agents carry a resolvable fill than the cap allows
- **THEN** the fullest agents up to the cap are drawn
- **AND** a count of the remaining agents is shown beside them

#### Scenario: The hidden agents are never the fullest

- **WHEN** the cap has hidden one or more agents
- **THEN** no hidden agent's fill is greater than any drawn agent's fill

#### Scenario: Unmeasured agents are counted, not dropped

- **WHEN** one or more agents are in the unmeasured state
- **THEN** they are reported by their own count or mark
- **AND** they are not silently omitted from the header

### Requirement: The fill and its window are computed once, server-side

The fleet payload SHALL carry each agent's resolved context window and its fill fraction, and the
browser SHALL NOT re-derive either from a model table of its own.

Two tables are two chances to disagree, and a header whose fraction contradicts the payload leaves
the reader unable to tell which to believe. This is the rule `cache_heat` already follows for
`cooled` and `cold`, held for the same reason.

#### Scenario: The payload states the window and the fill

- **WHEN** the fleet payload describes a live agent with a resolvable window
- **THEN** it carries that agent's context window and its fill fraction

#### Scenario: The payload states the unmeasured case

- **WHEN** an agent's window cannot be resolved or it carries no token figure
- **THEN** the payload marks it unmeasured rather than carrying a zero window or a zero fill
