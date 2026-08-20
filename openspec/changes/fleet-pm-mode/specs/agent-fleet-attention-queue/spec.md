## IN SCOPE
- What makes an agent an item in the attention queue, and what removes it
- The order items are presented in, and why it is not arrival order
- When a newly blocked agent may take over the screen, and when it may never
- What proves the reader dealt with the item on screen
- Deferral, demotion and the guarantee that nothing is dropped
- The history the reader steps back and forward through

## OUT OF SCOPE
- How a quiet agent's last turn is classified (`agent-fleet-pm-judgment`)
- How the item is rendered, and the toggle that turns the mode on (`agent-fleet-surface`)
- Measuring agent state from the session log (`agent-fleet-state`)
- Work awaiting a human with no agent on it — it cannot be answered in a terminal
- The work-cycle engine's `NEEDS_INPUT` questions, which have their own contract

## ADDED Requirements

### Requirement: The queue holds agents blocked on a person, never agents that are merely idle

The queue SHALL contain only agents whose next step is a person's answer. An agent that finished
its turn and asked nothing SHALL NOT be an item in it, and SHALL be reported as a separate count
that the reader may open deliberately.

The distinction is the whole product. Measured 2026-08-20 on this machine: of 17 quiet agents, 12
had ended with an agent utterance and most of those were completion reports. Queueing those makes
the reader acknowledge a dozen "done" messages before reaching a real question, and under this
capability's own freeze rule they would sit in front of the questions rather than beside them.

#### Scenario: A completion report is not queued
- **WHEN** an agent's last turn ended with a report and no request for a person
- **THEN** it is not an item in the queue, and it is included in a separate idle count

#### Scenario: A question is queued
- **WHEN** an agent's last turn ends with a question, a decision to take, or missing information
- **THEN** it is an item in the queue

#### Scenario: A working agent is never queued
- **WHEN** an agent has an outstanding tool call that is not itself a question to a person
- **THEN** it is not an item in the queue, whatever any other source says about it

### Requirement: The queue is ordered by freshness of the blockage, not by arrival

Within a project, the queue SHALL order items by how recently the agent became blocked, most
recent first. The framework SHALL NOT order by how long an item has been waiting.

This inverts the usual fairness rule and it is deliberate. The reason is a cost, not a preference:
an agent answered while its prompt cache is still warm resumes from that cache, and one answered
long after re-reads its whole context. The framework SHALL NOT assume any particular cache
lifetime, but the ordering follows its direction.

The price is starvation, and the next requirement is what pays it.

#### Scenario: A fresh blockage outranks an old one
- **WHEN** one agent became blocked two minutes ago and another forty minutes ago
- **THEN** the two-minute-old blockage is presented first

#### Scenario: A project is exhausted before the next one is entered
- **WHEN** more than one project holds queued items
- **THEN** every item of the presented item's project is offered before an item of another project

### Requirement: Nothing leaves the queue except by being dealt with

An item SHALL leave the queue only when the agent it names has resumed, when that agent is gone,
or when the reader dismisses it explicitly. Preemption, deferral and stepping back through history
SHALL NOT remove an item.

An item that is demoted SHALL still be counted and SHALL still be reachable. A queue that silently
drops what the reader skipped is indistinguishable from a queue that never held it.

#### Scenario: A preempted item returns
- **WHEN** the item on screen is preempted by a fresher blockage
- **THEN** it returns to the queue, ranked below where it was, and remains counted

#### Scenario: A dismissed item is not silently forgotten
- **WHEN** the reader dismisses an item without answering it
- **THEN** it leaves the queue and the count of dismissed items is reported

#### Scenario: A vanished agent is removed
- **WHEN** the agent an item names is no longer running
- **THEN** the item leaves the queue, and its removal is not reported as an answer

### Requirement: Only the agent resuming proves the reader dealt with the item

The framework SHALL treat an item as dealt with only when the agent it names has **resumed** — a
new assistant utterance, or a new outstanding tool call, recorded after the blockage. The framework
SHALL NOT treat the appearance of a new user entry in the session log as proof.

Measured on a live log (`itline-web/349ee01c…jsonl`, 2026-08-19): an interrupt writes a `user`
entry whose text is `[Request interrupted by user]`. Under the naive test that reads as an answer,
so pressing `Esc` would advance the queue — breaking the freeze this mode exists to provide. A
list of such synthetic markers is a second copy that drifts; measuring the effect does not.

#### Scenario: An interrupt does not advance the queue
- **WHEN** the reader interrupts the presented agent and types nothing further
- **THEN** the item stays on screen and the queue does not advance

#### Scenario: A real answer advances the queue
- **WHEN** the presented agent produces a new utterance or opens a new tool call after the blockage
- **THEN** the item is dealt with and the next item is presented

#### Scenario: A slash command that produces no turn does not advance the queue
- **WHEN** a log entry is written that does not cause the agent to resume
- **THEN** the item stays on screen

### Requirement: Typing suspends every switch, unconditionally

While the reader has sent input to the presented agent's terminal within a declared recent window,
the framework SHALL NOT switch the presented item, SHALL NOT start a countdown, and SHALL NOT
prompt. The window SHALL be a declared value; its default SHALL be 20 seconds.

This is the hard guarantee, and it is separate from the courtesy countdown below. A mode that can
pull the screen out from under a half-typed answer is a mode people turn off.

#### Scenario: A fresher blockage cannot interrupt typing
- **WHEN** an agent becomes blocked while the reader is typing into the presented terminal
- **THEN** nothing changes on screen and no countdown appears

#### Scenario: The window is measured from the last keystroke
- **WHEN** the reader stops typing and the declared window elapses with no further input
- **THEN** the presented item becomes eligible for preemption

### Requirement: A fresher blockage may take an idle screen, after a countdown any key cancels

When the presented item has received no input for the declared window and an agent becomes blocked
more recently than the presented one, the framework SHALL offer to switch after a declared
countdown. Its default SHALL be 5 seconds. **Any** input into the presented terminal SHALL cancel
the countdown and restart the typing window; an explicit dismissal SHALL cancel it and SHALL NOT
offer that same item again while the presented item is unchanged.

The countdown is a courtesy, not the safety mechanism — the typing window above is. Making the
countdown the guard would require the reader to watch for it, which is the behaviour that makes
such modes intolerable.

#### Scenario: A silent screen is preempted
- **WHEN** the reader has not typed for longer than the window and a fresher blockage exists
- **THEN** a countdown is shown naming what would be switched to, and the switch happens when it expires

#### Scenario: Typing during the countdown cancels it
- **WHEN** the reader types anything into the presented terminal while the countdown is running
- **THEN** the countdown is cancelled and the typing window restarts

#### Scenario: Dismissing the countdown does not re-offer the same interruption
- **WHEN** the reader dismisses the countdown explicitly
- **THEN** that item is not offered again until the presented item changes

### Requirement: A deferred item is demoted, not merely returned

An item the reader was shown and did not deal with SHALL be ranked below items the reader has not
seen when it re-enters the queue. The framework SHALL record that it was presented and SHALL
report how many times.

A reader who sat silently in front of an item is evidence about that item: they are not going to
answer it now. Returning it to the same rank presents it first again on the next cycle, which is
the loop the freeze rule would otherwise create.

#### Scenario: A twice-presented item ranks below an unseen one
- **WHEN** an item has been presented and not dealt with, and an unseen item of the same project exists
- **THEN** the unseen item is presented first

### Requirement: The reader can step back through what was already presented

The framework SHALL keep the order in which items were presented and SHALL let the reader move
back to an earlier one and forward again. Moving back SHALL NOT mark anything dealt with, and
moving forward SHALL be possible only as far as the item the queue currently presents.

#### Scenario: Stepping back re-presents an earlier item
- **WHEN** the reader steps back
- **THEN** the previously presented item is shown, and the queue does not advance

#### Scenario: Forward is bounded by the queue's own position
- **WHEN** the reader steps forward from an earlier item
- **THEN** they reach at most the item the queue currently presents

### Requirement: The queue holds identities and verdict classes, never session text

The queue's state SHALL carry the agent's identity, its project, the class of blockage and the
timestamps needed to order it. It SHALL NOT carry the session excerpt, the question text, or any
other verbatim content, in memory or on disk.

The text this mode reasons about is written inside projects that are not this framework's. The
persistence boundary allows it to be **displayed** and forbids it being **written down**, so the
queue is rebuilt from live sources on every cycle rather than saved and restored.

#### Scenario: Restarting loses the queue and not the work
- **WHEN** the service restarts
- **THEN** the queue is empty until the next cycle rebuilds it from live sources

#### Scenario: No queue record carries session content
- **WHEN** the queue's state is inspected
- **THEN** it contains no excerpt, question text or other verbatim session content
