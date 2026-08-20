## IN SCOPE
- Which agents a judgment pass is allowed to consider, and which it must skip
- That one pass covers every candidate, rather than one watcher per agent
- The classes a pass may return, and what happens to one it does not recognise
- That the judgment is advisory over a structural floor it can never override
- What a failed or unavailable pass must report
- The model role, and the persistence boundary the pass's input imposes

## OUT OF SCOPE
- Ordering, preemption, freezing and history (`agent-fleet-attention-queue`)
- Measuring an agent's state from its session log (`agent-fleet-state`)
- Any rendering (`agent-fleet-surface`)
- Classifying anything other than an agent's own session — the engine's questions
  arrive already structured and are not judged here

## ADDED Requirements

### Requirement: One pass per cycle covers every candidate

The framework SHALL classify all candidates of a cycle in a single model invocation. It SHALL NOT
start a watcher, a session or an invocation per agent.

The cost of the alternative is the reason: a per-agent watcher multiplies by the fleet's size, and
the fleet is 18 agents on this machine today with no upper bound in the design.

#### Scenario: Many candidates, one invocation
- **WHEN** a cycle has more than one candidate
- **THEN** exactly one model invocation is made for that cycle

#### Scenario: No candidates, no invocation
- **WHEN** a cycle has no candidates
- **THEN** no model invocation is made

### Requirement: The pass is stateless, and what the queue remembers lives in code

Each pass SHALL be independent of every earlier pass. What has already been presented, answered,
deferred or dismissed SHALL be held by the framework and SHALL NOT be carried in the model's
context.

A long-lived session accumulating a day of fleet output compacts, and a compacted context keeps
its confidence while losing its precision — which is exactly the failure that would make the queue
re-present items it had already shown. A fact held in code is re-derivable; a fact held in a
model's memory is not.

#### Scenario: A pass does not depend on the previous one
- **WHEN** two consecutive cycles run
- **THEN** the second invocation carries no state from the first

### Requirement: The candidate filter is structural, and it runs before the model

A candidate SHALL be an agent that is quiet, that does not itself owe the next utterance, whose
session log has changed since it was last judged, and whose blockage the framework has not already
determined structurally. Every other agent SHALL be excluded before the invocation is built.

The filter is what makes one pass per cycle affordable, and each of its four tests removes a class
the model could only agree with: a working agent is not blocked, an agent mid-turn cannot be
waiting on a person whatever its last words were, an unchanged log yields the same verdict, and a
structurally certain blockage needs no opinion.

`quiet` means only that no tool call was open at the log's last flush, and that is weaker than it
sounds: measured 2026-08-20, the runtime writes a `tool_use` together with its `tool_result`, so an
agent running a command for ten minutes carries no outstanding call and reads as quiet. Whose turn
it is survives that gap — after a tool result, and after a person's prompt, the next word is the
agent's.

#### Scenario: A working agent is not a candidate
- **WHEN** an agent has an outstanding tool call that is not a question to a person
- **THEN** it is not included in the invocation

#### Scenario: An agent that owes the next utterance is not a candidate
- **WHEN** an agent's session log ends with a tool result, or with a person's prompt it has not answered
- **THEN** it is not included in the invocation, whatever its last utterance said

#### Scenario: An agent that spoke last remains a candidate
- **WHEN** an agent's session log ends with the agent's own utterance
- **THEN** it is included in the invocation

#### Scenario: An unchanged log is not re-judged
- **WHEN** an agent's session log has not changed since its last verdict
- **THEN** it is not included in the invocation, and its previous verdict stands

#### Scenario: A structurally certain blockage skips the model
- **WHEN** an agent is measured as blocked on a person by its outstanding tool call
- **THEN** it is queued without being included in the invocation

### Requirement: The judgment is advisory over a structural floor it cannot override

Where the framework has measured an agent's blockage structurally, that measurement SHALL decide,
and a model verdict SHALL NOT remove it from the queue or change its class. A model verdict SHALL
only add items the structural pass cannot reach.

The two are different kinds of knowledge. An outstanding question tool is a fact about the log; a
verdict about prose is an opinion about meaning, and an opinion may not overturn a measurement.

#### Scenario: A model verdict cannot unqueue a measured blockage
- **WHEN** the model classifies a structurally blocked agent as not needing a person
- **THEN** the agent remains queued as blocked, and the disagreement is recorded

### Requirement: The classes are declared, and an unrecognised one is reported

A verdict SHALL name one of the classes this capability declares: blocked on a person, finished
without a question, or stopped for another reason. A verdict naming anything else SHALL be
reported as unrecognised and SHALL NOT be mapped onto the class it most resembles.

Mapping an unknown verdict onto a neighbour is how a model's confusion becomes the framework's
confident wrong answer, and the direction that hurts is mapping an unrecognised class onto
"finished", which makes an agent needing a person disappear.

#### Scenario: An unrecognised class is surfaced
- **WHEN** a verdict names a class this build does not know
- **THEN** the agent is reported as unclassified and is not silently treated as finished

#### Scenario: A missing verdict is not a negative verdict
- **WHEN** a candidate is included in the invocation and no verdict comes back for it
- **THEN** that agent is reported as unclassified, never as finished

### Requirement: A pass that could not run says so, and never renders as calm

When a pass fails, times out, or cannot be made, the framework SHALL report that the judgment is
unmeasured and SHALL keep the verdicts of the previous pass standing. It SHALL NOT present an
empty queue that its own measurement did not produce.

A gap is not a zero. "Nothing needs you" and "we could not look" lead to opposite actions, and the
first is the one a reader acts on by walking away.

#### Scenario: A failed pass is visible
- **WHEN** the model invocation fails
- **THEN** the mode reports the judgment as unmeasured, distinctly from an empty queue

#### Scenario: Previous verdicts survive a failed pass
- **WHEN** a pass fails and an earlier pass had queued items
- **THEN** those items remain queued

### Requirement: The judging model is a declared role

The model used SHALL be resolved through the framework's existing model-role configuration under
its own role name, and SHALL NOT be named in the code that builds the invocation. Its default
SHALL be the mid-tier model.

#### Scenario: The role is configurable
- **WHEN** the role's model is changed in configuration
- **THEN** the next pass uses the configured model with no code change

### Requirement: The framework persists nothing the pass reads

The invocation's input carries verbatim session content from projects that are not this
framework's. The framework SHALL NOT write that content — nor any part of a verdict quoting it —
into any log, record, cache, memory or file **of its own**. Diagnostics SHALL name counts, agent
identities and classes only.

**The runtime's own session journal is a named exception, and it is the only one.** Invoking a
model writes the prompt into that runtime's session log by construction — measured:
`run_claude_logged` tags each prompt so *"the session JSONL can be matched back to its caller"*
(`lib/set_orch/subprocess_utils.py:387`). Requiring otherwise would forbid using a model at all.
The exception is bounded by what it actually adds: the same content already exists in the judged
agents' own session logs on the same machine, and this adds a second machine-local copy under this
framework's attribution. It SHALL NOT be widened — no framework log, no cache, no queue record, no
committed artifact, and nothing that leaves the machine.

#### Scenario: The invocation body is never in a framework log
- **WHEN** a pass runs, succeeds or fails
- **THEN** no log line the framework emits contains session content from any candidate

#### Scenario: Verdicts are stored as classes, not as text
- **WHEN** a verdict is retained between cycles
- **THEN** what is retained is the class and the identity, not the reasoning text

#### Scenario: The exception does not extend beyond the runtime's own journal
- **WHEN** the pass's input or a verdict's reasoning would be written anywhere other than the
  runtime's session journal
- **THEN** it is not written
