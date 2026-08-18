## IN SCOPE
- Running one work unit in a fresh agent context and closing it with a verdict
- Locking a work unit to one seat so two runs cannot share a tree
- A schema-constrained verdict, and diffing that verdict against what the tree actually shows
- Running the gate through the project profile, and committing only behind a green gate
- Recording the verdict before the gate, so an interrupted run is still attributable

## OUT OF SCOPE
- Chaining several work units in a loop (later change)
- Reconciling an interrupted run back into a commit (later change)
- Run history and its query surface (later change)
- The phase lane and the lens lane — the abstraction admits them, this change does not ship them

## ADDED Requirements

### Requirement: A work unit runs in a fresh full agent context
The engine SHALL run each work unit as a full agent session, not as a subagent, so that hooks, rule
injection and gates apply to it exactly as they do to an interactive run. The engine SHALL stream the
session's events rather than waiting for a final message, so a running unit is observable while it
runs.

#### Scenario: Unit runs as a full session
- **WHEN** the engine starts a work unit
- **THEN** it launches a full agent session with the project's hooks and rules active
- **AND** it consumes the session's event stream as the run proceeds

#### Scenario: Progress is measured from the tree, not from the transcript
- **WHEN** the engine reports how far a unit has got
- **THEN** the figure is derived from completed task markers in the change's `tasks.md`
- **AND** the count of turns or events is NOT presented as progress

### Requirement: A work unit is locked to one seat, and the seat is session-scoped
The engine SHALL hold a lock for the duration of a work unit so that two units cannot run against the
same working tree. The seat identifier recorded in that lock SHALL identify a single agent session.
A seat identifier that names only the project SHALL be rejected.

#### Scenario: A second unit is refused while one runs
- **WHEN** a work unit is started while another holds the lock for the same tree
- **THEN** the engine refuses the second unit and names the holder

#### Scenario: A project-scoped seat is refused
- **WHEN** a seat identifier is supplied that identifies the project rather than a session
- **THEN** the engine refuses to record it
- **AND** the refusal states that a seat must identify one session

#### Scenario: A lock whose holder is gone does not block forever
- **WHEN** a lock exists but the process that took it is no longer alive
- **THEN** the engine reports the lock as stale rather than as running
- **AND** the stale state is distinguishable from a live run in the engine's own output

### Requirement: The verdict is schema-constrained
The engine SHALL require each work unit to return a verdict matching a declared schema, carrying at
minimum an outcome of `GROUP_DONE`, `PARTIAL`, `NEEDS_INPUT` or `BLOCKED`, and a summary. Open
decisions SHALL be carried in their own field, never inferred from free-text notes.

#### Scenario: A verdict outside the schema is refused
- **WHEN** a work unit returns output that does not match the verdict schema
- **THEN** the engine records the run as failed to report rather than inventing an outcome

#### Scenario: An open decision in the notes does not stop the cycle
- **WHEN** a unit describes a decision needing a human in its free-text notes but leaves the open
  decisions field empty
- **THEN** the engine does NOT treat it as a stop point
- **AND** the notes are carried forward as context only

#### Scenario: An open decision in its own field stops the unit
- **WHEN** a unit returns one or more entries in the open decisions field
- **THEN** the engine marks the corresponding work as awaiting a human answer

### Requirement: The verdict is checked against the tree
The engine SHALL compare what the verdict claims was completed against the task markers actually
present in `tasks.md`, and SHALL report divergence in **both** directions — claimed but unmarked, and
marked but unclaimed.

#### Scenario: Claimed more than was marked
- **WHEN** the verdict lists completed work that the file does not mark as complete
- **THEN** the engine reports the discrepancy and does not adopt the claim

#### Scenario: Marked more than was claimed
- **WHEN** the file marks work complete that the verdict does not mention
- **THEN** the engine reports that discrepancy too

### Requirement: The gate is the project's own, declared first and detected only as a fallback
The engine SHALL take its gate steps from the project's adoption declaration when the project
declares the key, and SHALL fall back to the resolved project profile only when the project has not
declared it. The engine SHALL NOT contain project-specific commands, file paths or tooling names.
A project that ends up with no gate steps SHALL run with no gate rather than with a guessed one.

Declaring the key empty is an answer and SHALL be honoured as one: the engine SHALL NOT consult the
profile in that case. A deliberately narrowed gate that is silently widened produces a green
indistinguishable from the project's own gate having passed.

#### Scenario: The declared commands are the ones that run
- **WHEN** an adopted project declares gate steps and a work unit finishes
- **THEN** the commands executed are exactly the ones the project declared
- **AND** no command detected from the profile is executed

#### Scenario: An explicitly empty declaration is not answered a second time
- **WHEN** an adopted project declares the gate key with no steps
- **THEN** the engine runs no gate and records that no gate was run
- **AND** it does NOT consult the profile for a detected command

#### Scenario: Gate steps come from the profile when the project declared none
- **WHEN** an adopted project does not declare the gate key at all
- **THEN** the steps executed are those the project's profile declares

#### Scenario: No declared gate means no gate
- **WHEN** neither the project nor the profile yields a gate step
- **THEN** the engine runs no gate and records that no gate was run
- **AND** it does NOT substitute a default command

### Requirement: A red gate holds the chain, whatever the task markers say
A group whose last recorded run ended on a failed gate SHALL NOT be treated as complete, and
groups depending on it SHALL stay blocked, even when every one of its tasks is marked done.
The engine SHALL name that reason rather than reporting the group as complete. A later run of
the same group that ends on a passing gate SHALL clear the hold.

#### Scenario: Every task marked, gate red
- **WHEN** a group's tasks are all marked done but its last run's gate failed
- **THEN** the group is reported as NOT complete, naming the failed gate as the reason
- **AND** no group depending on it becomes runnable

#### Scenario: A green re-run releases the group
- **WHEN** the same group is run again and its gate passes
- **THEN** the hold is gone and dependent groups become runnable

### Requirement: A hold can be discharged without starting a work unit
The engine SHALL provide a way to re-run the gate of a group held by a failed one, without
starting an agent session and without creating a new work unit. A held group has no open
tasks left, so the start path cannot reach it, and the gate is the only thing that can clear
the hold; without this the hold is a deadlock rather than a guard.

A green re-check SHALL clear the hold and SHALL commit work the failed gate left in the tree.
Where no group is held, the re-check SHALL run no gate at all.

#### Scenario: The cause was fixed elsewhere
- **WHEN** a group is held by a failed gate and the cause has since been fixed
- **THEN** re-running the gate alone clears the hold, with no agent session started
- **AND** the report names what was cleared, not only the record

#### Scenario: Nothing is held
- **WHEN** no group is held by a failed gate
- **THEN** the re-check runs no gate command and changes no record

### Requirement: The engine does not commit its own run records
When committing a unit's work, the engine SHALL exclude its own run-state directory from what
it stages. The directory is the engine's own bookkeeping, and a project adopting the engine
SHALL NOT have to exclude it on its side.

#### Scenario: A unit's work is committed
- **WHEN** the engine stages a unit's changes
- **THEN** its run-state directory is excluded from the staged set

### Requirement: The engine never reports a tree state it did not measure
When a gate fails, the engine SHALL check whether the tree has moved since the unit started
before stating that the work stays in the tree. Where the unit's agent has committed the work
itself, the engine SHALL report that fact in a dedicated field of the run record — not only in
prose — and SHALL NOT claim the work is being held for review.

The engine SHALL NOT be assumed to prevent such a commit: a unit's agent holds the same tools
the engine does, so "commit only behind a green gate" binds the engine, not the agent.

#### Scenario: The agent committed before the gate ran
- **WHEN** a gate fails and the tree's HEAD has moved since the unit started
- **THEN** the record names the commit the agent made, in a field of its own
- **AND** the record does NOT state that the work stays in the tree

### Requirement: A failure is attributed elsewhere only on positive evidence
The engine SHALL attribute a gate failure to the unit only where the files a failure names
intersect the files the unit changed. Where they do not intersect, the engine SHALL report
the attribution as undetermined — NOT as elsewhere — unless the unit changed no file at all,
which is positive evidence of innocence.

A set of files scraped from gate output SHALL NOT be treated as a list of causes: it may
carry names taken from prose and from passing steps, and a cause may be indirect and
therefore unnameable by any filename intersection. Paths resolving to the tree root SHALL be
excluded.

#### Scenario: No intersection is not innocence
- **WHEN** a gate failure names only files this unit did not change
- **THEN** the attribution is undetermined and says why a clean intersection proves nothing

#### Scenario: A unit that changed nothing
- **WHEN** a gate fails and the unit changed no file in the tree
- **THEN** the attribution is elsewhere, and names that as the evidence

#### Scenario: The tree root is not a named file
- **WHEN** the gate output contains a bare `.` or `./`
- **THEN** no empty path enters the implicated set

### Requirement: A commit happens only behind a green gate
The engine SHALL commit a work unit's changes only after its gate has passed. When the gate fails,
the engine SHALL leave the work in the tree, SHALL NOT commit, and SHALL NOT advance to the next
unit.

#### Scenario: Gate fails
- **WHEN** the gate reports a failure
- **THEN** no commit is made
- **AND** the work remains in the working tree
- **AND** the engine stops rather than starting the next unit

#### Scenario: Gate passes
- **WHEN** the gate passes
- **THEN** the engine commits the unit's changes with a reference to the change and unit it belongs to

### Requirement: The verdict is durable before the gate runs
The engine SHALL record the verdict durably **before** running the gate, so that a run interrupted
between the verdict and the commit is still attributable to the unit that produced the work.

#### Scenario: Killed between verdict and commit
- **WHEN** the engine's process ends after a unit returns its verdict but before the commit completes
- **THEN** the recorded verdict survives
- **AND** the engine's later output shows a started unit with no completion, rather than showing the
  unit as never attempted

### Requirement: A gate failure states whether it came from this unit's own work
When a gate fails, the engine SHALL report which of the three attributions applies, because a tree
may hold work the engine did not do and does not control. It SHALL NOT attribute a failure to the
unit without that distinction.

⚠ This requirement states the *obligation to attribute*; **when `elsewhere` is permitted is decided
by "A failure is attributed elsewhere only on positive evidence" above, and that requirement wins.**
A scenario stood here saying that a failure naming only other files is reported as originating
outside the unit — it was the shipped behaviour until it was measured to exonerate on the absence of
evidence, and it survived here beside its own replacement, contradicting it. Two requirements each
internally consistent is exactly the shape a traceability check cannot see: the matrix was complete
while the spec disagreed with itself. Do not restore it.

#### Scenario: Failure in the unit's own files
- **WHEN** a gate fails and the failure implicates files this unit changed
- **THEN** the engine attributes it to the unit

#### Scenario: Attribution cannot be determined
- **WHEN** the engine cannot establish which files a failure implicates
- **THEN** it says so
- **AND** it does NOT default to attributing the failure to the unit

### Requirement: A unit may take other units' verdicts as input, and setting it aside preserves them
A work unit's input MAY be the verdicts of other work units. When such a unit is set aside rather
than completed, the engine SHALL preserve each input verdict in full. A summary, a merged view or a
selected branch SHALL NOT replace the inputs, because what a reader needs at that point is where the
inputs diverged.

#### Scenario: Comparing unit is set aside
- **WHEN** a unit whose input is several other units' verdicts is set aside instead of producing an
  outcome
- **THEN** every input verdict remains retrievable in full
- **AND** no input verdict is replaced by a summary of it

#### Scenario: A mechanical projection of the comparison does not decide
- **WHEN** the comparison's result is projected into a single outcome for a caller
- **THEN** the projection carries the comparison's own verdict rather than deciding on its behalf
- **AND** where the comparison reached no decision, the projection is a stop rather than a choice
