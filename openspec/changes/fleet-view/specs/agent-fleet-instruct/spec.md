## IN SCOPE
- Delivering a typed or dictated instruction to a running agent
- Reporting which delivery outcome actually occurred
- Behaving defined when the messaging bus is absent or the agent is unreachable

## OUT OF SCOPE
- Typing directly into a session's terminal (`agent-fleet-terminal`, and impossible for a session
  the framework did not start — this capability is how every *other* agent is reached)
- Starting an agent, or restarting one that has exited (`agent-fleet-terminal`)
- Installing or configuring the messaging bus in a project without being asked
- Reading the agent's reply as anything other than new lines in its log

## ADDED Requirements

### Requirement: An instruction is delivered over the messaging bus

The framework SHALL deliver an instruction to a running agent by addressing it on the messaging
bus, and SHALL NOT attempt to write into the terminal of a process it did not start.

A session started elsewhere owns its terminal, and injecting input into a terminal the sender does
not own is refused by current kernels. This is a boundary of the system rather than an obstacle to
work around: any mechanism that appeared to bypass it would be relying on a configuration that is
off by default and off for a reason.

#### Scenario: An addressed instruction reaches an agent
- **WHEN** a caller sends an instruction to an agent that has a bus identity
- **THEN** the message is delivered addressed to that specific session, not broadcast to its project

#### Scenario: A broadcast is never a substitute for an address
- **WHEN** the intended agent's identity cannot be resolved
- **THEN** the send is refused and the reason reported, rather than sent to everyone in its room

### Requirement: The delivery report distinguishes every outcome, and an outcome can expire

The framework SHALL report which outcome occurred, and SHALL NOT report a single confirmation
covering all of them:

- **arrives now** — a waiter under that session can start a new turn
- **arrives at the end of the current turn** — the session is working, and its stop-hook will not
  let the turn close over unread addressed mail
- **sits unread** — the session is idle with no waiter, and nothing will start a turn until a person
  types into it
- **held pending the recipient's own human** — the channel refused to deliver automatically, and
  someone at the far end must approve it before the agent sees it at all

The outcome SHALL be taken from the channel's own answer about what it did, not inferred — and
specifically **not from the send call's own return value**, which reports that the message was
accepted for delivery rather than what became of it. Where an outcome can lapse, the framework SHALL
report the lapse as well, and SHALL NOT leave the earlier outcome standing as though it still held.

Measured, and it is the trap this requirement exists to close: the send returned `success: true`
immediately, while the real outcome — held, and later expired undelivered — arrived minutes
afterwards as two separate out-of-band notifications. A surface that reads the return value has
measured that the call was accepted, which is compatible with the message never reaching anyone.

Measured on one machine, 4 of 12 live sessions had a waiter of their own. A single "sent" would be
correct in a minority of cases and misleading in the rest — and misleading in the direction where
someone waits for an answer that is not coming.

**The fourth outcome was found by measurement after the first three were written, and it is the one
that breaks the shape of the report.** Sending into a live session over the runtime's own
cross-session channel produced neither delivery nor silence: the message was **held**, the
recipient's *human* was prompted to allow or deny it, and the recipient's state flipped to waiting
on that prompt. Held twice, on two sessions; **both holds then expired unanswered and the messages
were dropped**. So this outcome is not a fourth resting state — it is a state with a clock, and a
tile that renders it once is asserting something that stops being true without any further event.
The lapse arrives as its own notification and must be carried through to wherever the first outcome
was shown.

#### Scenario: An agent with a waiter
- **WHEN** the bus reports that the send woke the addressed session
- **THEN** the outcome is reported as arriving now

#### Scenario: A working agent without a waiter
- **WHEN** the bus reports no session woken and the agent's state is working
- **THEN** the outcome is reported as arriving at the end of the current turn

#### Scenario: An idle agent without a waiter
- **WHEN** the bus reports no session woken and the agent's state is not working
- **THEN** the outcome is reported as sitting unread until someone types into that session

#### Scenario: An unknown outcome is not upgraded to success
- **WHEN** the bus returns no usable answer about what it woke
- **THEN** the outcome is reported as unknown, and not as delivered

#### Scenario: The send call's success is not an outcome
- **WHEN** the send call returns successfully
- **THEN** nothing is reported as delivered on that basis alone, and the outcome remains pending
  until the channel says what became of the message

#### Scenario: A message held for the recipient's human
- **WHEN** the channel reports that it did not deliver the message and that someone at the receiving
  end must approve it first
- **THEN** the outcome is reported as held pending that approval, distinctly from delivered and from
  sitting unread

#### Scenario: A hold that lapses
- **WHEN** a held message expires without the recipient's human answering
- **THEN** the lapse is reported where the original outcome was shown, and the message is reported as
  not delivered

#### Scenario: A held message is never counted as reaching the agent
- **WHEN** a message is held
- **THEN** nothing reports the agent as having been instructed, because the agent has not seen it

### Requirement: A direct channel may ring the bell, but never carry the message

Where a lower-level channel to a running agent exists — a local socket the runtime itself
provides — the framework MAY use it to prompt an agent to check its mailbox, and SHALL NOT use it
to carry the instruction's content. The instruction itself always goes through the durable path.

The durable path leaves a record: the message is on disk, addressed, with a read cursor, so "who
has not seen this yet" remains answerable. A direct socket send is fire-and-forget — no record, no
cursor, and the surfaces that report unread work go blind to it. A surface whose whole rule is that
nothing may be hidden cannot deliver through a channel that leaves no trace.

It also fails well. If the direct channel turns out to be unusable from outside the runtime — it is
not a documented interface — the system still behaves exactly as it does without it: the message is
delivered and read at the next opportunity, only later.

#### Scenario: The durable send woke nobody
- **WHEN** an instruction is written to the durable channel and the reply reports that no session
  was woken
- **THEN** the framework may prompt that session over the direct channel to read its mailbox

#### Scenario: The content never travels on the direct channel
- **WHEN** the direct channel is used
- **THEN** it carries only a prompt to check the mailbox, never the instruction text

#### Scenario: The direct channel is unavailable
- **WHEN** the direct channel cannot be used at all
- **THEN** delivery still happens through the durable path, and the reported outcome says the
  message is waiting rather than that it failed

### Requirement: An orphaned waiter is shown, and removing it is an offer rather than a tidy-up

The framework SHALL report waiter processes whose session no longer exists, SHALL identify each one
by resolving it to a process identity rather than by counting matches, and SHALL remove one only on
an explicit action naming that process. It SHALL NOT remove waiters as a side effect of any other
action, SHALL NOT remove one whose session is alive, and SHALL treat an undeterminable session as
alive.

Measured alongside the delivery outcomes: roughly thirty waiters were running whose sessions had
died. They wake nothing and they do not clean themselves up, so they accumulate — and they sit
exactly where this capability reports that an agent has no waiter, which is the moment a reader is
being invited to install one. Showing the debris next to the offer is what makes the offer honest.

**The fail direction decides the design here, and it is not symmetrical.** Leaving an orphan costs a
process table entry. Killing a live waiter takes away the thing that would have delivered someone's
next instruction, silently, and the agent it belonged to then looks merely quiet. So every
uncertainty resolves toward *not removing*, and removal goes through the same ownership check as any
other write into a project that is not ours — it is not exempt for being a cleanup.

**And the identification is the part that has already gone wrong once.** The first count of these was
too optimistic because the counting command's own command line contained the pattern it searched
for, so it matched itself. A removal built on that class of check would aim at whatever the shell was
running at the time. Each candidate is therefore resolved to a process and confirmed against its
session before it is offered, and never taken from the number of lines a pattern returned.

#### Scenario: An orphan is reported next to the missing waiter
- **WHEN** a project holds waiter processes whose sessions have exited
- **THEN** they are reported, alongside the agents reported as having no waiter

#### Scenario: Removal is explicit and named
- **WHEN** an orphaned waiter is to be removed
- **THEN** it happens only on an action naming that specific process, and never as a side effect of
  installing a waiter or of any other operation

#### Scenario: A live waiter is never removed
- **WHEN** a candidate waiter's session is alive, or cannot be determined to be dead
- **THEN** it is not offered for removal and not removed

#### Scenario: A candidate is an identity, not a match count
- **WHEN** waiter candidates are gathered
- **THEN** each is resolved to a process and checked against its session, and no candidate comes from
  the number of matches a pattern returned

### Requirement: An agent that cannot be instructed says so where the input would be

When an agent has no bus identity — including when the bus is not installed in its project — the
framework SHALL report it as discoverable and observable but not instructable, and the surface
SHALL show the reason in place of the input rather than omitting the agent or hiding the control.

Measured: 3 of 12 live sessions had no bus identity. Dropping those agents would hide running work;
showing an input that silently goes nowhere would be worse. The absence is information, and it is
information at exactly the place where someone is about to type.

#### Scenario: An agent in a project without the bus
- **WHEN** an agent is discovered in a project where the messaging bus is not installed
- **THEN** it appears with its state and log, its input disabled, and the reason stated

#### Scenario: The bus is unavailable entirely
- **WHEN** no messaging bus is present on the machine
- **THEN** discovery and state still work for every agent, and every tile reports instruction as
  unavailable
