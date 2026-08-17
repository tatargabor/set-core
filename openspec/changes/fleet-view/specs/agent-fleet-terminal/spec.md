## IN SCOPE
- Starting an agent from the surface, under a pseudo-terminal the framework owns
- Streaming that terminal to a browser in both directions, so typing into it types into the agent
- The lifetime of a process the framework started: the browser closing, the service restarting, stopping it deliberately
- Whether an already-running session can be adopted into an owned terminal, and what happens if it cannot

## OUT OF SCOPE
- Typing into a session the framework did not start and cannot adopt (`agent-fleet-instruct` reaches those over the bus)
- Discovering agents (`agent-fleet-inventory`) or deriving their state (`agent-fleet-state`)
- Placement of the terminal on the screen (`agent-fleet-surface`)
- A terminal for anything other than an agent process — this is not a general shell service

## ADDED Requirements

### Requirement: A terminal exists only for a process the framework started or adopted

The framework SHALL attach a terminal only to an agent process it started itself under a
pseudo-terminal it owns, or to a session it has adopted by resuming it into such a process. It SHALL
NOT write into the terminal of any other process, and SHALL NOT report a terminal as available for
one.

Injecting input into a terminal the sender does not own is refused by current kernels. That is a
property of the system, not an obstacle to route around: any mechanism that appeared to bypass it
would depend on a setting that is off by default and off for a reason. So the population an agent
belongs to — started here, adopted, or foreign — decides whether a terminal can exist at all, and
that fact travels with the agent rather than being re-derived by each surface.

#### Scenario: A surface-started agent has a terminal
- **WHEN** an agent is started from the surface
- **THEN** it runs under a framework-owned pseudo-terminal, and a terminal is reported as available

#### Scenario: A foreign session has none
- **WHEN** an agent process was started outside the framework and has not been adopted
- **THEN** no terminal is reported for it, and no write into its terminal is attempted

#### Scenario: The reason is carried, not inferred
- **WHEN** a caller asks whether an agent can be typed into
- **THEN** the answer names which of the three populations it is in, rather than leaving the caller
  to guess from other fields

### Requirement: Adoption of a running session is measured before it is relied upon

Whether an already-running agent session can be adopted into a framework-owned terminal by resuming
it SHALL be established by measurement before any behaviour depends on the answer, and the outcome
SHALL be recorded in the change's design. Until it is established, the framework SHALL treat every
session it did not start as un-adoptable.

This is the one unknown on this capability's critical path. It is the difference between a terminal
that serves the whole fleet and one that serves only the sessions started from the screen — and
those are different features, not different sizes of the same one. Assuming the favourable answer
would be a plausible guess built on, which is precisely the failure this change's own evidence rules
were written against.

**The first route was measured and refuted** (design §6.1): resuming a session id while another
process holds it live returns success, exposes the intact history, reuses the same id and appends to
the same log — and forks the conversation into a second branch that the still-running original never
sees. The requirement stands unchanged for any *further* route proposed, and the standard it sets is
now concrete: a route counts as adoption only if the original session stops being a second writer.

#### Scenario: Adoption works
- **WHEN** measurement shows a running session can be resumed into an owned terminal without losing
  its history
- **THEN** adoption is offered for foreign sessions, and the resulting agent reports a terminal

#### Scenario: Adoption does not work
- **WHEN** measurement shows it cannot be done, or cannot be done without losing session state
- **THEN** foreign sessions keep the bus input, their tiles state that no terminal is possible, and
  the finding is written into the design with what was run and what it returned

#### Scenario: The unmeasured state is not the optimistic one
- **WHEN** the measurement has not been made
- **THEN** the framework behaves as if adoption is impossible, rather than offering a control whose
  outcome is unknown

### Requirement: Resuming a session that is running is refused, not offered

The framework SHALL NOT resume a session it can observe to be running, SHALL NOT expose a control
that would, and SHALL state that the session is live as the reason. A resume SHALL be permitted only
for a session with no live process writing it.

Resuming a live session does not fail. It succeeds, returns the history, keeps the session id, and
appends to the same log — while the running original continues on its own branch, unaware, and the
log becomes two branches under one name. Nothing reports it. Sampled on one machine, a quarter of
recent session logs already carry branches, so this is an ordinary state of the world rather than a
corner case, and the surface must not be a new source of it.

The reason it must be refused rather than merely discouraged is the direction of the damage: the
person who clicks it gets a plausible answer, and the agent that loses its continuity is a different
agent, on a different tile, belonging to someone who is not looking.

#### Scenario: A live session is not resumable from the surface
- **WHEN** an agent is discovered with a live process bound to its session log
- **THEN** no resume or adopt control is offered for it, and the reason given is that the session is
  running

#### Scenario: A dead session may be resumed
- **WHEN** a session log has no live process writing it
- **THEN** resuming it is permitted

#### Scenario: The refusal survives a stale binding
- **WHEN** it cannot be determined whether a session is still running
- **THEN** it is treated as running and the resume is refused, rather than attempted on the
  optimistic reading

### Requirement: Terminal traffic travels in both directions and is never persisted

The framework SHALL stream the agent's terminal output to the connected browser and SHALL deliver
the browser's keystrokes to that terminal, and SHALL NOT write terminal content to disk, to a cache,
to a log file, or into this repository.

A terminal carries everything a session log carries and carries it sooner — including whatever a
person types. The confidentiality boundary is about persistence rather than naming, so the traffic
is relayed and dropped. Diagnostics name the stream and the failure kind, never a line of content.

#### Scenario: Output reaches the browser
- **WHEN** the agent writes to its terminal
- **THEN** the connected browser receives that output

#### Scenario: Keystrokes reach the agent
- **WHEN** a key is typed into the connected terminal component
- **THEN** the agent process receives it as terminal input

#### Scenario: A failure reports shape, not content
- **WHEN** the stream fails or a frame cannot be decoded
- **THEN** the diagnostic names the stream and the failure kind, and quotes none of its content

#### Scenario: Nothing is kept
- **WHEN** a terminal session ends
- **THEN** no transcript of it remains on disk

### Requirement: A started agent's lifetime is defined for the browser leaving and the service restarting

The framework SHALL define, and report, what becomes of an agent it started when the browser
disconnects and when the service that started it restarts. An agent SHALL NOT be left running with
nothing able to reach it, and stopping one SHALL be an explicit action rather than a side effect of
closing a view.

An agent outliving the request that started it is the whole value of starting one here — and it is
also the orphan class this screen exists to make visible. Creating orphans from the surface built to
reveal them would be the same defect one layer up. Closing a tab is not an instruction to stop
working, so it must not be read as one, and the reverse — a process nobody can reach or stop — must
not be the price of that.

**A service restart is the case where those two pull against each other, and it took a measurement
and a decision to settle.** The terminal cannot survive it — its handle belongs to the process that
died (design §6.1). The agent's survival is not automatic either: measured, a child of the service
sits in the service's own cgroup and is killed with it, so the framework SHALL place a started agent
outside the lifetime of any service that could restart under it. With that done the agent keeps
running with no terminal, and it is not thereby unreachable: it keeps its bus identity, so it stays
observable and instructable by every other means this change provides, and it remains stoppable
deliberately. "Reachable" is a property of the agent, not of the terminal, and only the terminal
column changes to no.

#### Scenario: The browser disconnects
- **WHEN** the browser showing an agent's terminal closes
- **THEN** the agent keeps running, and is still listed with its terminal reattachable

#### Scenario: Reattaching after disconnect
- **WHEN** a browser reconnects to an agent the framework started
- **THEN** it attaches to the same terminal and the agent continues

#### Scenario: The service restarts
- **WHEN** the service that started an agent restarts
- **THEN** the agent is still running and still instructable, and its terminal alone is reported as
  gone — never as attachable

#### Scenario: An agent outlives the service that started it
- **WHEN** any service in the framework restarts, including the one that owns agent lifetime
- **THEN** an agent started from the surface keeps running, because it was placed outside that
  service's lifetime rather than inside it

#### Scenario: A terminal handle is never reacquired from outside
- **WHEN** any path would try to take over a terminal by reopening another process's descriptor
- **THEN** it is not attempted, and the terminal is reported gone while the agent stays listed and
  instructable

#### Scenario: Stopping is deliberate
- **WHEN** an agent started here is to be stopped
- **THEN** it stops on an explicit action, and never as a consequence of a view being closed

### Requirement: The terminal is proven by driving it as a person drives it

The proof that a terminal works SHALL be an assertion that a keystroke entering the browser-side
terminal component reaches the agent process and that the agent's output returns to that component.
Writing to the pseudo-terminal's file descriptor from the test process SHALL NOT be accepted as
proof.

A test that writes to the descriptor exercises a path the user does not have, and passes identically
on a build where the browser is wired to nothing. The negative half is asserted the same way: for an
agent the framework did not start, the surface offers no terminal at all — a check that only
confirms the positive case would pass on a build that offers a terminal for every agent.

#### Scenario: A keystroke makes the round trip
- **WHEN** a key is entered into the terminal component in a browser
- **THEN** the agent process receives it, and its response appears in that same component

#### Scenario: The negative case is asserted too
- **WHEN** the tests run against an agent the framework did not start
- **THEN** no terminal is offered for it, and this is asserted rather than assumed
