## IN SCOPE
- A pre-push gate layer for this repository: where gates live, how they are run, what they report
- Per-gate baselines that record existing debt and may only shrink
- A deliberate-skip path, and what using it must leave behind
- The shared matching library every gate uses for the things that keep being got wrong

## OUT OF SCOPE
- The orchestration engine's integration gates, which run at merge time on a consumer project
- Deploying this layer into consumer projects — a separate change with its own safety argument
- Guarding commits: only pushes are gated, deliberately
- What any individual gate checks (`rule-enforcement-gates`, `adversarial-spec-review`)

## ADDED Requirements

### Requirement: Gates run before a push and fail closed

The repository SHALL run its gates before a push, and a failing gate SHALL stop the push. A gate
SHALL report what failed, where, and what would resolve it. Commits SHALL NOT be gated.

Pushes rather than commits, because a commit is a working step and a push is where work leaves the
machine — and because the framework's own rule already forbids bypassing pre-push hooks for exactly
this reason: a bypassed push silently skips every chain hanging off it.

#### Scenario: A violation stops the push
- **WHEN** a gate detects a violation
- **THEN** the push does not proceed, and the output names the file, the rule and the remedy

#### Scenario: A clean push is not slowed by ceremony
- **WHEN** no gate detects a violation
- **THEN** the push proceeds and the layer reports only that it passed

#### Scenario: Committing is unaffected
- **WHEN** work is committed locally
- **THEN** no gate runs

### Requirement: A gate that meets existing debt carries a baseline, and the baseline may only shrink

A gate introduced against existing violations SHALL carry a baseline listing them, seeded from the
measured state at introduction. The layer SHALL reject a baseline that has grown relative to its
committed previous version, unless growth is requested explicitly and visibly.

Measured before this layer existed: 404 exception handlers that swallow silently, and 24 changes with
started work and no review artifact. A gate switched on against those numbers blocks the next push,
and the outcome is not that the debt is repaid — it is that the skip is made permanent within a day.
A baseline makes the gate land without blocking and turns the debt into a number that can only go
down. It may only shrink because a growable baseline is a gate that can be switched off one line at a
time, by the person the gate exists to stop.

#### Scenario: Existing debt does not block
- **WHEN** a gate is introduced and its baseline lists the current violations
- **THEN** pushes continue to pass while those violations remain

#### Scenario: A new violation is blocked
- **WHEN** a violation appears that is not in the baseline
- **THEN** the gate blocks

#### Scenario: Growing the baseline is refused by default
- **WHEN** a baseline gains an entry relative to its committed previous version
- **THEN** the layer blocks and names the added entries

#### Scenario: Growth is possible but explicit
- **WHEN** growth is requested through the explicit mechanism
- **THEN** it is allowed, and the request is visible in the change that made it

#### Scenario: An identifier that changes form is still matched
- **WHEN** a baselined item's identifier acquires a prefix or suffix through a normal lifecycle step
- **THEN** the baseline still matches it, rather than turning a known-debt entry into a new failure

### Requirement: Skipping is possible, deliberate and recorded

The layer SHALL provide a way to skip a gate for a push, and using it SHALL require an explicit
action that leaves a record of the reason.

A layer with no escape hatch is disabled wholesale the first time it is wrong. The requirement is not
that skipping be hard, but that it be visible: a skip that leaves no trace is indistinguishable from
a gate that never ran.

#### Scenario: A skip is available
- **WHEN** a gate must be bypassed for a legitimate reason
- **THEN** an explicit mechanism allows it

#### Scenario: A skip leaves a trace
- **WHEN** a gate is skipped
- **THEN** the fact and its reason are recorded where a reviewer will see them

### Requirement: Gates match content through a shared library, not by ad-hoc pattern

Gates SHALL use a shared matching library for reading structured claims out of documents, and that
library SHALL exclude fenced code blocks from what it treats as data and SHALL match whole lines
where a marker is meant to be a line.

Both behaviours are corrections for measured failures rather than precautions. An example inside a
fenced block has already been read as a directive by this project's own delta parser. And a marker
matched as a substring reads a quoted verdict as a verdict — a documented case where a change whose
own header declared it blocked passed the gate that existed to stop it, because the gate matched one
shape of finding and the file used another.

#### Scenario: An example is not data
- **WHEN** a document contains a fenced block showing a violating example
- **THEN** the gate does not treat it as a violation

#### Scenario: A quoted marker is not a verdict
- **WHEN** a marker appears inside a sentence that quotes or negates it
- **THEN** it is not matched as a verdict

#### Scenario: Several shapes of the same claim are recognised
- **WHEN** a status appears as a table row in one document and as a heading or list item in another
- **THEN** the gate recognises both, because the writer chooses the form and the gate must not

### Requirement: A prose signal warns and does not block until it is measured to be right

Where a gate can only infer a violation from prose, it SHALL warn rather than block, and SHALL be
promoted to blocking only after measurement shows the signal is right at least half the time over a
sustained period.

Measured on the adopted implementation: 4 of 7 prose hits were rule quotations or references to an
already-resolved state, and the negated form means the opposite of the plain one. A blocking check
built on that fires mostly on quotations, and a gate that fires on nothing is skipped by everyone
within a week — which is worse than not having it, because its presence implies a check.

#### Scenario: An inferred violation warns
- **WHEN** a gate infers a violation from prose alone
- **THEN** it prints a warning and the push proceeds

#### Scenario: Promotion is earned
- **WHEN** a warning signal is measured to be correct at least half the time over a sustained period
- **THEN** it may be promoted to blocking, and the measurement is recorded
