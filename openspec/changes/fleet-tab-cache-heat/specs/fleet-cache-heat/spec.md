## IN SCOPE

- Reading a session's prompt-cache state from the native transcript it already writes
- Exposing that state on the fleet agent record, in a shape that can say "unknown"
- Marking cooling, stake, and rewrite cost on the agent tab
- One dated table for the price multipliers and per-model input prices

## OUT OF SCOPE

- Any new instrumentation: no hook, no wrapper, no second store — the transcript is the source
- Predicting or preventing cache expiry, warming a cache, or advising the reader to act
- Subagent caches: a tab stands for the session the reader types into
- Cost of output tokens, or any billing figure beyond the input-cache arithmetic

## ADDED Requirements

### Requirement: A session's prompt-cache state is read from the transcript it already writes

The framework SHALL derive a session's prompt-cache state from the last assistant record in that
session's native transcript, and SHALL introduce no other mechanism to obtain it. That record
carries everything needed: the request's start timestamp, `cache_read_input_tokens`,
`cache_creation_input_tokens`, and a `cache_creation` breakdown naming which lifetime was written.

The derived state SHALL consist of the request's START time, the cache size in tokens
(`cache_read_input_tokens` + `cache_creation_input_tokens`), and the lifetime read from the record.

The start time is the correct reference and not an approximation of one: an entry's lifetime runs
from the moment the request that wrote or read it BEGAN, and generation time counts against it.
Deriving it from the record's own timestamp is therefore exact for the question being asked, and
a session mid-generation reads slightly colder than it is — an error in the safe direction.

#### Scenario: A session that has made a request

- **WHEN** the last assistant record of a session's transcript carries a usage block with cache figures
- **THEN** the session's cache state names that record's timestamp, the sum of its cache read and
  cache creation tokens, and the lifetime that record wrote

#### Scenario: The lifetime is read, never assumed

- **WHEN** a record's `cache_creation` reports tokens written under the one-hour lifetime and none
  under the five-minute one
- **THEN** the state names one hour, and the framework does not substitute a lifetime of its own

### Requirement: A session with no measurement is representable, and is not a cold one

The cache state SHALL be ABSENT — distinguishable from every measured value — when there is no
transcript for the session, when the transcript holds no assistant record with cache figures, or
when the record cannot be read. It SHALL NOT be reported as a zero-token cache, a zero age, or
any other value that a measurement could also produce.

A gap is not a zero, and here the two would carry opposite meanings: a zero-size, long-ago cache
reads as "cold, cheap to restart", while the truth is "we have not measured this seat at all".

#### Scenario: A seat that has never run

- **WHEN** a discovered agent has no transcript on disk
- **THEN** its record carries no cache state, rather than a cache state with zero size

#### Scenario: A transcript with no usage records

- **WHEN** a transcript exists but holds no assistant record carrying cache figures
- **THEN** its record carries no cache state

### Requirement: The tab marks how far its cache has cooled

An agent tab SHALL carry a bar along its bottom edge whose FILLED FRACTION is how far the session's
cache has cooled: empty when the last request has just started, complete when the lifetime has
elapsed. The bar SHALL fill from the leading edge toward the trailing one, and SHALL remain fully
drawn once the lifetime has elapsed rather than disappearing.

Filling with the cooling rather than emptying with the remaining time is what keeps a healthy tab
quiet: a fresh seat carries no mark at all, so the mark's presence already means something. And a
mark that stays after expiry is what stops the surface from looking the same for a cold cache and
an unmeasured one.

The bar's colour SHALL follow that same fraction across three bands, so the state is legible
without hovering, comparing, or counting.

#### Scenario: A freshly used session

- **WHEN** a session's last request started moments ago
- **THEN** its tab's bar is empty

#### Scenario: A session partway through its lifetime

- **WHEN** half of a session's cache lifetime has elapsed
- **THEN** its tab's bar is drawn to about half its width, in the band that fraction falls in

#### Scenario: A session past its lifetime

- **WHEN** more time has passed than the session's cache lifetime
- **THEN** the bar is fully drawn and stays drawn, in the final band

### Requirement: The mark carries the stake as well as the time

The bar's THICKNESS SHALL encode the cache size, so that two tabs at the same point in their
lifetime are distinguishable by how much each stands to lose.

Time alone is not the decision. Measured on this machine, live sessions held between roughly
fifteen thousand and two hundred thousand tokens — a thirteenfold spread — and a mark that ignores
it reports two very different losses identically. Thickness is used because it is orthogonal to the
bar's length, which the cooling fraction has already claimed.

#### Scenario: Two tabs, same age, different caches

- **WHEN** two sessions are equally far through their lifetimes but one holds several times the
  tokens of the other
- **THEN** the larger session's bar is drawn thicker

### Requirement: A cold tab says so in more than one way, and the ways cannot disagree

When a session's cache lifetime has elapsed, the tab SHALL mark this in its NAME as well as in its
bar, and SHALL show the cost of rewriting that cache beside the name. While the cache is still
live, that cost SHALL NOT be shown.

Every one of these marks SHALL be driven by the SAME single condition. Two marks computed
separately are two chances to disagree, and a tab whose bar is full while its name is not — or
whose price contradicts its colour — is worse than either mark alone, because the reader cannot
tell which one to believe.

The price appears only once the cache is cold because only then does it decide anything: while the
cache lives, its read cost is what the reader pays regardless of what they do.

#### Scenario: A cold tab

- **WHEN** a session's cache lifetime has elapsed
- **THEN** the tab's name is marked as cold, its bar is fully drawn, and the rewrite cost is shown
  beside the name

#### Scenario: A live tab

- **WHEN** a session's cache is still within its lifetime
- **THEN** the tab's name carries no cold marking and no cost is shown

### Requirement: A tab with no measurement is marked unknown, never cold

A tab whose session has no cache state SHALL be marked as unmeasured, distinctly from both a live
and a cold tab, and SHALL carry neither a bar nor a cost.

This is the surface half of "a gap is not a zero". An unmeasured seat rendered as cold invites the
reader to avoid a tab for a cost nobody computed; rendered as live, it invites them to type into
one whose cost is unknown. Saying so is the only honest option.

#### Scenario: An unmeasured seat

- **WHEN** an agent's record carries no cache state
- **THEN** its tab shows an unmeasured marking, with no bar and no cost

### Requirement: The exact figures are reachable without acting

The tab SHALL make the precise remaining time, the cache size in tokens, and the cost available on
hover, for every state including the unmeasured one.

The bar answers "roughly how far along"; a decision needs "eight minutes, then $1.96". Hover is the
right home for it because reading it is already an act of attention, whereas the bar has to be
legible when nobody is looking at it.

#### Scenario: Hovering a live tab

- **WHEN** the reader hovers a tab whose cache is still live
- **THEN** the remaining minutes, the cache size, and the rewrite cost are stated

#### Scenario: Hovering an unmeasured tab

- **WHEN** the reader hovers a tab with no cache state
- **THEN** it states that the cache was not measured, and offers no figure

### Requirement: Prices come from one dated table, and a missing price degrades to tokens

The framework SHALL hold the cache price multipliers and the per-model input prices in a SINGLE
place that records the date its figures were verified, and SHALL NOT scatter them across the code
that uses them.

A published price is a measurement with a date, and the transcript names the model but not what it
costs. When a model has no entry in the table, the framework SHALL present the cache SIZE and
SHALL NOT present a fabricated cost.

#### Scenario: A model the table does not know

- **WHEN** a session's model has no entry in the price table
- **THEN** the tab presents the cache size in tokens and no monetary figure

#### Scenario: The table states its own date

- **WHEN** the price table is read
- **THEN** the date on which its figures were verified is recorded alongside them

### Requirement: Nothing measured from a session is written down

Cache state SHALL be computed for display and SHALL NOT be persisted: not into this repository, not
into a committed artifact, and not into any cache, log, or debug dump that can leave the machine.

The figures are derived from consumer sessions as well as this project's own, and the boundary this
framework draws is persistence rather than naming. A size and an age look harmless, which is exactly
why the rule has to be stated where the reading happens.

#### Scenario: The state is displayed and discarded

- **WHEN** cache state is computed for a fleet of agents
- **THEN** it reaches the surface and is written to no file
