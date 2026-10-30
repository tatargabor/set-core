## IN SCOPE
- The declared read command `owner-queue`: a ranked, cross-project list of items for the owner
- The declared write command `owner-queue-act`: the card's actions handed back to the publisher
- The item shape the framework reads, and the markers for incomplete or stale answers
- Which project publishes the queue, and what happens when none or several do

## OUT OF SCOPE
- How the publisher ranks (an agent, a formula, a person — the framework reads the order only)
- Where the publisher gets its items (meetings, inboxes, lists — project-side)
- Any change to the status contract's envelope, versioning, transport or caveats

## ADDED Requirements

### Requirement: `owner-queue` is an ordinary declared read command

A project SHALL publish the owner queue by declaring a read command named `owner-queue` under the
existing status contract. The framework SHALL read it through the contract's reader and SHALL keep no
built-in list of which project publishes it.

#### Scenario: A project declares the command
- **WHEN** a registered project's endpoint declares `owner-queue` in its read list
- **THEN** the card reads that project's answer as the owner queue

#### Scenario: Two projects declare it
- **WHEN** two registered projects declare `owner-queue`
- **THEN** the card uses the one named in local configuration
- **AND** when none is named, it shows neither and states that the publisher is ambiguous

### Requirement: The owner-queue item shape

The answer's `data` SHALL carry `items`, in rank order, each with: `id` (opaque, stable across
answers), `project`, `sentence` (one imperative sentence), `why` (one line), and optionally
`estimateMinutes`, `deadline`, `unblocks` (a short count description), `options` (a list of
`{ id, label }`), `acceptsText`, `delegable`, `link`, and `references` (a list of `{ source, id }`
naming framework items it covers). `data` SHALL also carry `complete` and `rankedAt`. The framework
SHALL treat every text field as display-only.

#### Scenario: A minimal item
- **WHEN** an item carries only `id`, `project`, `sentence` and `why`
- **THEN** the card shows it with Done, Not needed and Later and no other actions, and Go there only when the item carries a `link`

#### Scenario: Options are present
- **WHEN** an item carries three options
- **THEN** the card shows three option buttons

### Requirement: Incomplete and stale answers are marked, not hidden

When `complete` is false the card SHALL show that the queue is partial. When `rankedAt` is older than
a configured age the card SHALL show the age of the ranking on the card. Neither condition SHALL hide
items.

#### Scenario: A stale ranking
- **WHEN** `rankedAt` is six hours old and the configured age is two hours
- **THEN** the card shows "ranked 6 h ago" next to the item

### Requirement: `owner-queue-act` receives the card's actions

A project that publishes `owner-queue` SHALL declare a write command named `owner-queue-act`. The
framework SHALL call it through the contract's existing write path with the action object
`{ id, action, option?, text?, reasons?, until? }` serialised as one JSON value under a single `json`
argument, so that lists and free text survive the write path's argument mapping; `action` is one of
`answer`, `done`, `delegate`, `park-idea`, `resume-note`, `wind-down-handoff`. A successful call
answers with the contract envelope and MAY carry `data.outcome`, a one-line text the card shows as
feedback. A failure SHALL be reported with the project's own reason, under the contract's existing
write-failure rules — including a refusal by the framework's own write path, which SHALL be shown
as such and never silently worked around.

*Amended 2026-10-29 after the publisher was built and measured against the framework's reader:* the
write path maps arguments to `--flag value` and refuses values that begin with `-`, and
`parse_envelope` requires `ok` plus `data`, so the outcome lives in `data.outcome`, not at the top
level.

#### Scenario: An answer with an outcome
- **WHEN** the card sends `{ id, action: "answer", option: "b" }` and the command answers with `data.outcome` "agent resumed"
- **THEN** the card shows "agent resumed"

#### Scenario: No write command is declared
- **WHEN** the publisher declares `owner-queue` but not `owner-queue-act`
- **THEN** the card shows items with Go there and Later only
- **AND** it states that the publisher accepts no actions

### Requirement: The publisher's shape is agreed before the adapter is built

The item shape in this capability is a proposal. The framework's adapter SHALL NOT be built until the
publishing project has answered on the bus; where the publisher already produces an equivalent list,
its field names SHALL be adopted and this capability amended to them.

#### Scenario: The publisher proposes different names
- **WHEN** the publisher answers that its list already uses `title` instead of `sentence`
- **THEN** the capability is amended to `title` before the adapter is written

### Requirement: An item can be re-checked on demand, and says when it was recommended

*Added 2026-10-30. The owner, looking at a card: «kellene egy pontos idő is, mikori az ajánlás, és
egy gomb, hogy ellenőrizze a háttérben, tényleg aktuális-e … de találjuk ki, hogyan nem lesz
tokenkazán».*

An item MAY carry `firstSeen` (when the publisher first recommended it) and `check`
(`{ state, startedAt, at?, evidence? }`, `state` one of `running`, `stands`, `rewritten`, `stale`,
`failed`). The card SHALL show the exact clock time of `firstSeen` and of the ranking. The action
list of `owner-queue-act` SHALL include `recheck`, which asks the publisher to verify ONE item in the
background; it SHALL NOT close the item. The cost of a check is the publisher's to bound; the card
SHALL send a recheck only on the owner's tap, never on its own, and SHALL show the publisher's
outcome (including a refusal such as a daily limit) verbatim.

#### Scenario: Asking whether an item is still current
- **WHEN** the owner taps "Still current?" on an item
- **THEN** `{ id, action: "recheck" }` is sent, the outcome is shown, and the item stays

#### Scenario: A check reports the premise is gone
- **WHEN** an item carries `check.state: "stale"` with evidence
- **THEN** the card shows that it is no longer current with the evidence and the time of the check, and leaves closing it to the owner

#### Scenario: The exact time
- **WHEN** an item carries `firstSeen` and the answer carries `rankedAt`
- **THEN** the card shows both as clock times, not only as an age
