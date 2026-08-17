## IN SCOPE
- Reading numbered task groups and their dependency edges out of a change's `tasks.md`
- Fail-closed ordering: an unannotated group waits for its predecessor
- Choosing which group is runnable now
- Cutting the slice one run receives, and the carry-over that travels with it
- Assembling the reading list a run is given

## OUT OF SCOPE
- Ordering changes relative to one another (already covered by the existing dependency handling
  between changes)
- Executing the group — that is the work-unit engine's concern
- Rewriting or reformatting a project's `tasks.md` beyond marking task state

## ADDED Requirements

### Requirement: Task groups are read from the change's task file
The resolver SHALL read a change's `tasks.md` and identify its groups from numbered headings, and
SHALL associate every task line with exactly one group.

#### Scenario: Groups are identified
- **WHEN** a `tasks.md` contains numbered group headings with task lines beneath them
- **THEN** the resolver reports one group per heading, each carrying its own task lines

#### Scenario: Tasks outside any group
- **WHEN** task lines appear before the first group heading
- **THEN** the resolver reports them as a group rather than discarding them

### Requirement: Dependency edges are declared, and their absence is fail-closed
The resolver SHALL read dependency edges from an annotation attached to a group. A group carrying no
annotation SHALL be treated as depending on the group before it. Independence SHALL only be
concluded from an explicit declaration of it.

#### Scenario: Declared dependencies
- **WHEN** a group declares that it depends on specific earlier groups
- **THEN** the resolver treats it as runnable only once those groups are complete

#### Scenario: No annotation means serial
- **WHEN** a group carries no dependency annotation
- **THEN** the resolver treats it as depending on the immediately preceding group

#### Scenario: Explicit independence
- **WHEN** a group explicitly declares that it has no dependencies
- **THEN** the resolver treats it as runnable regardless of earlier groups

#### Scenario: A cycle is reported, not silently ordered
- **WHEN** declared dependencies form a cycle
- **THEN** the resolver reports the cycle and declares no group runnable
- **AND** it does NOT pick an arbitrary order

### Requirement: The next runnable group is selected deterministically
The resolver SHALL select the next runnable group as the lowest-ordered group that has open tasks,
whose dependencies are satisfied, and which is not awaiting an answer. Given the same file it SHALL
return the same selection.

#### Scenario: Dependencies unsatisfied
- **WHEN** the lowest-ordered group with open tasks depends on a group that still has open tasks
- **THEN** it is not selected

#### Scenario: A group awaiting an answer is skipped, not blocked behind
- **WHEN** a group is awaiting a human answer and a later independent group is runnable
- **THEN** the later group is selected
- **AND** the awaiting group remains reported as awaiting

#### Scenario: Nothing runnable
- **WHEN** every group with open tasks is either blocked by dependencies or awaiting an answer
- **THEN** the resolver reports that no group is runnable, and why for each

### Requirement: A run receives its slice, not the whole file
The resolver SHALL provide the selected group's block as the work description handed to a run, and
SHALL NOT hand over the full task file. Where a caller limits the number of tasks, the slice SHALL
be cut to that limit within the group.

#### Scenario: Only the group's block is handed over
- **WHEN** a group is selected for a run
- **THEN** the handed-over work description contains that group's tasks
- **AND** it does not contain other groups' tasks

#### Scenario: Hard slicing within a group
- **WHEN** a caller limits a run to a number of tasks smaller than the group
- **THEN** the slice contains at most that many open tasks from the group

### Requirement: Carry-over travels from the previous run
The resolver SHALL provide, alongside the slice, the notes of the most recent completed run for the
same group and the notes of the most recent completed run for the preceding group. Older runs' notes
SHALL NOT be included.

#### Scenario: Resuming a partial group
- **WHEN** a group is selected that a previous run left partially complete
- **THEN** that previous run's notes travel with the new slice

#### Scenario: Discoveries reach the next group
- **WHEN** a group is selected whose predecessor produced notes
- **THEN** those notes travel with the slice

#### Scenario: Stale notes are dropped
- **WHEN** several earlier runs exist for the same group
- **THEN** only the most recent one's notes are included

### Requirement: The reading list includes the change's own artifacts
The resolver SHALL include, in the material a run is given, every markdown artifact in the change's
directory other than the task file itself, including artifacts produced by earlier runs of the same
change.

#### Scenario: An artifact produced by an earlier group is included
- **WHEN** an earlier run wrote a new markdown artifact into the change's directory
- **THEN** a later run's reading list includes it

#### Scenario: The task file is not duplicated
- **WHEN** the reading list is assembled
- **THEN** the task file is excluded, because the slice is handed over separately
