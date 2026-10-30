## IN SCOPE
- The declared read command `owner-calls`: the calls the owner should make, and why
- The declared write command `owner-calls-act`: the owner's answer on a call handed back
- The call shape the framework reads, and the markers for incomplete or stale answers

## OUT OF SCOPE
- Where the publisher finds calls (mail, notes, dictations, a phone system) — the framework shows what it is given
- Placing a call: the card shows the number as a `tel:` link and nothing more
- How a retry or a snooze is scheduled on the publisher's side

## ADDED Requirements

### Requirement: `owner-calls` is an ordinary declared read command

*Added 2026-10-30 at the owner's request: «kellene egy olyan tab is, hogy milyen hívásokat kellene
csinálnom és kivel. pl. visszahívni valakit, akit ígértem, vagy nem vette fel, vagy én nem».*

A project SHALL publish the owner's calls by declaring a read command named `owner-calls` under the
existing status contract. The framework SHALL find its publisher the same way it finds the
`owner-queue` and `owner-goals` publishers — the one declaring project, or the one named in local
configuration — and SHALL keep no built-in list of projects.

#### Scenario: No project declares it
- **WHEN** no registered project declares `owner-calls`
- **THEN** the Calls tab states that no call list is published, without a failure marker, and the other tabs are unaffected

### Requirement: The call shape

The answer SHALL carry `calls`, a list in the order the owner should make them. A call SHALL have
`id`, `who`, `about` and `kind` (one of `promised`, `retry`, `missed`, `follow-up`), and MAY carry
`phone`, `due` (a date or a date-time), `project`, `attempts`, `lastAttempt`, `firstSeen` and up to
four `evidence` entries `{ label, link? }`. A call missing a required field, or repeating an id,
SHALL be skipped and counted, never shown half; a malformed optional field SHALL be dropped and the
call kept. Every text field is display-only: the framework SHALL NOT log or persist it.

#### Scenario: A malformed call
- **WHEN** one call in the answer has no `who`
- **THEN** the other calls are shown and the tab says one call was unreadable

#### Scenario: An overdue call
- **WHEN** a call's `due` has passed (a bare date: once that day has ended)
- **THEN** the call and the tab's count are marked overdue

### Requirement: Incomplete and stale call answers are marked, not hidden

A failed read SHALL be shown as a failure on the Calls tab's label, so it is visible from the other
tabs. An answer with `complete: false` or `unreadSources` SHALL be marked partial, and an answer whose
`rankedAt` is older than the ranking's stale threshold SHALL be marked stale.

#### Scenario: The read fails
- **WHEN** the `owner-calls` command fails
- **THEN** the Calls tab label carries a failure marker and the tab names the reason

### Requirement: `owner-calls-act` receives the owner's answers

The card SHALL send the owner's answer through the declared write command `owner-calls-act` as one
`--json` argument `{ id, action, text?, until? }`, with `action` one of `called` (text: how it went,
optional), `no-answer` (the call stays and comes back), `later` (with `until`) and `not-needed`. The
card SHALL show the publisher's outcome verbatim, show a refusal with its reason without hiding it,
and re-read the calls after a delivered answer. Without a declared write command the calls SHALL be
read-only and say so.

#### Scenario: Called, with a note
- **WHEN** the owner taps Called, writes how it went, and presses Enter
- **THEN** `{ id, action: "called", text }` is sent, the outcome is shown, and the list is re-read

#### Scenario: No answer
- **WHEN** the owner taps No answer
- **THEN** `{ id, action: "no-answer" }` is sent and the call is not closed by the card
