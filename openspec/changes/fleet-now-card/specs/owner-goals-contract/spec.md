## IN SCOPE
- The declared read command `owner-goals`: the owner's current goals, and the publisher's advice on what they should be
- The declared write command `owner-goals-act`: the owner's confirmations and verdicts handed back
- The goal and advice shapes the framework reads, and the markers for incomplete or stale answers

## OUT OF SCOPE
- How the publisher finds or judges goals (an agent, a formula, a person — the framework shows what it is given)
- Where the goals are stored, and how a confirmed goal outlives the next synthesis (project-side)
- Linking queue items to goals beyond the count the publisher supplies

## ADDED Requirements

### Requirement: `owner-goals` is an ordinary declared read command

*Added 2026-10-30. The owner asked for the Now card to show "what are the ten big goals we are working
on now", synthesised from the work on the machine, and — in a second message — for the synthesiser to
say what the goals SHOULD be.*

A project SHALL publish the owner's goals by declaring a read command named `owner-goals` under the
existing status contract. The framework SHALL find its publisher the same way it finds the
`owner-queue` publisher — the one declaring project, or the one named in local configuration — and
SHALL keep no built-in list of projects.

#### Scenario: The queue's publisher also declares goals
- **WHEN** the project that declares `owner-queue` also declares `owner-goals`
- **THEN** the card's Goals tab reads that project's answer

#### Scenario: No project declares it
- **WHEN** no registered project declares `owner-goals`
- **THEN** the Goals tab states that no goals are published, and the Now tab is unaffected

### Requirement: The goal and advice shapes

The answer's `data` SHALL carry `goals`, in the publisher's order, each with `id` (opaque, stable
across answers), `title` (one sentence) and `status` (`proposed` or `confirmed`), and optionally
`why`, `serves` (the parent goal's label), `deadline`, `progress` (`{ text, done?, total? }`),
`projects` (names), `evidence` (a list of `{ label, link? }`) and `openItems` (how many queue items
serve it). `data` SHALL also carry `advice`, a list of `{ id, kind, sentence, why, goalId? }` where
`kind` is one of `add`, `drop`, `merge`, `reorder`, `neglected`, `other`, and `synthesizedAt` and
`complete`. Every text field SHALL be display-only. An entry missing a required field SHALL be
skipped and counted, never shown half.

#### Scenario: A proposed goal
- **WHEN** a goal carries `status: "proposed"`
- **THEN** the tab marks it unconfirmed and offers Keep, Not a goal and Rename

#### Scenario: Advice
- **WHEN** the answer carries two advice entries
- **THEN** the tab shows them under "Suggestions", each with its reason and Accept / Decline

### Requirement: Incomplete and stale goal answers are marked, not hidden

When `complete` is false the tab SHALL say the goals are partial and name the publisher's unread
sources. When `synthesizedAt` is older than a configured age the tab SHALL show the age. Neither
condition SHALL hide goals. When the read fails, the failure SHALL be marked on the tab itself, so it
is visible from the Now tab.

#### Scenario: The goals cannot be read
- **WHEN** the `owner-goals` command fails while the Now tab is open
- **THEN** the Goals tab label carries a failure marker

### Requirement: `owner-goals-act` receives the owner's verdicts

A project that publishes `owner-goals` SHALL declare a write command named `owner-goals-act`. The
framework SHALL send `{ id, action, text? }` as one JSON value under a single `json` argument — the
same write path and argument shape as `owner-queue-act` — where `action` is `keep`, `drop` or
`rename` (text required) for a goal, and `accept` or `decline` for an advice entry. A success MAY
carry `data.outcome`, shown as feedback; a refusal SHALL be shown with the project's own reason.

#### Scenario: Keeping a proposed goal
- **WHEN** the owner taps Keep on a proposed goal
- **THEN** the write command receives `{ id, action: "keep" }` and the tab re-reads the goals

#### Scenario: No write command is declared
- **WHEN** `owner-goals` is declared without `owner-goals-act`
- **THEN** the goals are shown read-only and the tab says the publisher accepts no verdicts
