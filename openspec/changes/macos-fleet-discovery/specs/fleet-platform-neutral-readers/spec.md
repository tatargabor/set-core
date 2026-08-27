## IN SCOPE
- What `discovery`, `instruct` and `purpose` report on macOS once they read through the source.
- That each reader's existing fail direction survives the move.
- That the already-working macOS waiter reader is consolidated without changing its answers.
- What counts as evidence that a blind reader stopped being blind.

## OUT OF SCOPE
- The source contract and backend selection — see `fleet-process-source`.
- Which macOS command answers what — see `macos-process-reader`.
- Any change to what the fleet does with a fact: git resolution, session-record binding,
  waiter panel layout, tile ordering.
- Improving `parent_seat`'s answer. It returns `None` correctly on Linux for a documented
  reason; this only stops it returning `None` blindly.

## ADDED Requirements

### Requirement: Agent discovery reports live agents on macOS

`discover_agents()` SHALL report every live interactive agent session on macOS with the same
fields it reports on Linux — pid, working directory, resolved project, kind, and the session
binding where a record exists.

Measured before this change on a machine running two real agent sessions: `discover_agents()`
returned `[]`, `is_agent_process()` returned `False` for a live agent pid, and the fleet screen
rendered "0 agents" as though it were a count. It was a blind read presented as a measurement,
which is the false-absence class rather than a display bug.

`discover_agent(pid)` SHALL likewise re-verify a pid on macOS rather than rejecting every pid,
so that a per-agent route resolves instead of returning nothing.

#### Scenario: Live agents are listed on macOS
- **GIVEN** at least one live interactive agent session on a macOS machine
- **WHEN** agents are discovered
- **THEN** that session appears with its correct working directory
- **AND** its kind is reported as interactive

#### Scenario: A live pid verifies as an agent on macOS
- **WHEN** `is_agent_process` is asked about the pid of a live agent on macOS
- **THEN** it returns true

#### Scenario: A one-shot subprocess is still excluded by default
- **GIVEN** an agent process started with a one-shot flag
- **WHEN** agents are discovered without requesting one-shots
- **THEN** that process is not listed

#### Scenario: A pid that is not an agent is still rejected
- **WHEN** `discover_agent` is asked about a live pid that is not an agent
- **THEN** it returns nothing

### Requirement: Ancestry is answered from measurement rather than from absence

`parent_seat(pid)` SHALL climb the process tree on macOS using the source's parent-pid
operation.

This requirement exists because the function's correct answer and its blind answer are the
same value. It returns `None` on Linux for a documented and measured reason — 0 of 23 live
agents had an agent ancestor, and a framework-started agent's parent is the owner process —
so a test asserting `None` on macOS would pass against an implementation that never looked.
Verification SHALL therefore assert that the ancestry walk was actually performed, not only
that the returned value is `None`.

#### Scenario: The walk reaches an agent ancestor when one exists
- **GIVEN** a process whose ancestor chain contains a live agent
- **WHEN** its parent seat is resolved on macOS
- **THEN** that agent's seat is returned

#### Scenario: No agent ancestor is reported as none, having looked
- **GIVEN** a live process with no agent among its ancestors
- **WHEN** its parent seat is resolved on macOS
- **THEN** nothing is returned
- **AND** the parent-pid operation was invoked at least once

### Requirement: Recorded runs report their true status on macOS

`purpose` SHALL determine whether a recorded run's pid is alive, and whether it is an agent,
through the source rather than by testing for a `/proc` directory.

Measured before this change: `_pid_state()` returned `(False, False)` for a live agent pid on
macOS, because `/proc/<pid>` cannot exist there. Every recorded run therefore reported `stale`
— "nothing is running", stated about a machine where something was.

The existing precedence SHALL be preserved exactly: a run with a commit or a set-aside marker
is `finished` whatever its pid now belongs to, and only then is the pid consulted.

#### Scenario: A live run is running, not stale
- **GIVEN** a recorded run whose pid is a live agent on macOS
- **WHEN** its status is read
- **THEN** it is reported as running

#### Scenario: A finished run stays finished
- **GIVEN** a recorded run carrying a commit
- **WHEN** its status is read on macOS
- **THEN** it is reported as finished
- **AND** its pid is not consulted

#### Scenario: An exited run is stale
- **GIVEN** a recorded run whose pid no longer exists
- **WHEN** its status is read on macOS
- **THEN** it is reported as stale

### Requirement: Waiter removal resolves a waiter on macOS

`remove_waiter(pid)` SHALL read the candidate's argument vector and its session through the
source, so that a genuine waiter on macOS can be identified and removed.

Measured before this change: the argument vector read from `/proc` was always empty, so every
pid failed the waiter test and the function refused with "this pid is not a waiter process".
The refusal was the safe direction and nothing was killed wrongly — but the control was
permanently dead and its message named the wrong reason.

Every existing refusal SHALL be preserved. In particular the function SHALL still refuse when
session liveness is undeterminable, when the waiter's own session cannot be read, and when
that session is alive.

#### Scenario: A real waiter is identified on macOS
- **GIVEN** a live waiter process on macOS whose session is not alive
- **WHEN** its removal is requested
- **THEN** it is removed

#### Scenario: A non-waiter pid is still refused, for the right reason
- **WHEN** removal is requested for a live pid that is not a waiter
- **THEN** it is refused
- **AND** the reason names that the pid is not a waiter

#### Scenario: An alive session still blocks removal
- **GIVEN** a live waiter whose session is among the live sessions
- **WHEN** its removal is requested
- **THEN** it is refused
- **AND** the reason names that its session is alive

#### Scenario: An unreadable session still blocks removal
- **GIVEN** a live waiter whose session cannot be determined
- **WHEN** its removal is requested
- **THEN** it is refused

### Requirement: The existing macOS waiter reader is consolidated without changing its answers

The macOS readers already present in `instruct` SHALL move into the platform backend so that
there is one implementation of each fact rather than two that can drift apart. The move SHALL
NOT change what `live_waiters()` returns on either platform.

Two implementations of "the working directory of a pid on macOS" will diverge, and the one
that diverges will be the one nobody is looking at — `live_waiters()` already works, so
nothing draws attention to it.

#### Scenario: Waiters are unchanged by the consolidation
- **GIVEN** a live waiter process on macOS
- **WHEN** live waiters are read after the consolidation
- **THEN** the same pid, session, working directory and rooms are reported as before it

#### Scenario: The Linux waiter reader is unchanged
- **GIVEN** a fake `/proc` tree containing a waiter process
- **WHEN** live waiters are read with that tree as the root
- **THEN** the same waiter is reported as before the consolidation

### Requirement: The Linux behaviour is preserved and is proven by untouched tests

Every existing test that drives a reader against a fake `/proc` tree SHALL continue to pass
**without being edited**. An edit to one of those tests SHALL be treated as evidence that the
abstraction moved a contract, and SHALL be justified in the change rather than made silently.

#### Scenario: The /proc fixture suites pass unedited
- **WHEN** the existing fleet discovery, instruct and purpose suites are run after the change
- **THEN** they pass
- **AND** their files are unmodified by this change

#### Scenario: An explicit root still selects the Linux reader on macOS
- **GIVEN** a fake `/proc` tree built by a test running on macOS
- **WHEN** a reader is driven with that tree as its root
- **THEN** it reads that tree

### Requirement: The screen is looked at before this is called done

A non-zero agent count SHALL NOT be accepted as evidence that this change worked. The fleet
screen SHALL be opened in a browser against the running dashboard and looked at, and what was
seen SHALL be stated.

Structural counts and passing suites answer whether a mechanism ran; the defect this change
repairs was in the result. If the browser cannot be reached, the verification SHALL remain
open and SHALL be reported as open, in the tasks and in the commit — never substituted with a
test count.

#### Scenario: The fleet screen is verified visually
- **WHEN** the fleet screen is opened on a macOS machine with live agents
- **THEN** the agents are visible with their projects
- **AND** what was seen is recorded

#### Scenario: An unreachable browser leaves the check open
- **WHEN** the browser cannot be reached
- **THEN** the visual verification is reported as not performed
- **AND** it is not marked complete on the strength of passing tests
