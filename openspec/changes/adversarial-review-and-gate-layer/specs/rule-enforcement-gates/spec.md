## IN SCOPE
- The first concrete gates, each enforcing a rule this project already states
- The gate that enforces the adversarial review's artifact
- How each of them is scoped so it is passable on the day it lands

## OUT OF SCOPE
- Domain gates from the project this layer was adopted from — pricing, document numbering, ticketing, persistence-stack safety
- Web-shaped gates (endpoint auth, UI entry points, test ids, design tokens): candidates for a project-type module, not for the core
- The layer's own mechanics: baselines, skipping, matching, self-tests

## ADDED Requirements

### Requirement: A change with started work carries its review artifact

The layer SHALL fail when a change has started work — a task marked done or in progress — and its
directory holds no substantive review artifact, and SHALL apply the same check to changes archived
within the pushed range.

The archived half is not an edge case. Without it, implementing and immediately archiving is a
complete way around the review, and it is the path taken by exactly the work that is in a hurry. A
substantive artifact means one carrying severity markers or an explicit statement of no findings; an
empty file satisfies existence and nothing else.

#### Scenario: Started work without a review is blocked
- **WHEN** a change has a completed task and no review artifact
- **THEN** the push is blocked, naming the change

#### Scenario: An empty artifact does not satisfy the gate
- **WHEN** a review artifact exists but contains no severity marker and no statement of no findings
- **THEN** the gate treats it as absent

#### Scenario: Archiving does not bypass the review
- **WHEN** a change is archived within the pushed range and holds no review artifact
- **THEN** the push is blocked

#### Scenario: An unresolved critical finding blocks the push
- **WHEN** a review artifact records a critical finding whose status is still open
- **THEN** the push is blocked until the status records resolution or a stated rejection

### Requirement: An error is not swallowed silently

The layer SHALL fail when an exception handler is introduced whose entire body discards the error
without logging it.

The project's code-quality rule already forbids this. Measured before this gate existed: 404 such
handlers across 83 files, none of them reported by anything. A silent handler is the single most
expensive shape in a parallel orchestration, because the failure it hides surfaces later, somewhere
else, as a symptom with no cause attached.

#### Scenario: A new silent handler is blocked
- **WHEN** a new exception handler discards its error with no logging
- **THEN** the gate blocks and names the location

#### Scenario: Existing ones do not block
- **WHEN** a handler is listed in the gate's baseline
- **THEN** it does not block, and remains counted as debt

#### Scenario: A handler that logs is accepted
- **WHEN** a handler records the error at any level before continuing
- **THEN** the gate accepts it

### Requirement: A touched change validates

The layer SHALL run the project's own change validation, in its strictest mode, against the changes
modified in the pushed range, and SHALL fail when one of them does not validate. Changes not touched
by the push SHALL NOT be validated.

Measured: 14 of 36 active changes do not validate strictly. A gate demanding all of them be fixed
before any push is a gate nobody can pass on the day it lands; one demanding that the change being
worked on is clean is always passable and makes the number monotonically decrease.

#### Scenario: A touched invalid change blocks
- **WHEN** a change modified in the pushed range fails strict validation
- **THEN** the push is blocked with the validator's own output

#### Scenario: Untouched debt does not block
- **WHEN** a change that the push does not modify fails validation
- **THEN** the push proceeds

### Requirement: A rule does not cite a file that does not exist

The layer SHALL fail when a rule document cites a repository path that does not exist.

Measured: 14 of 46 paths cited across the rule corpus do not resolve. The cost is not tidiness — a
rule is followed by reading it, and a citation into nothing sends the reader to re-derive what the
rule was trying to hand them, which is how a rule quietly stops being applied while still being
present.

#### Scenario: A dead citation blocks
- **WHEN** a rule document cites a path that does not exist
- **THEN** the gate blocks and names both the rule and the path

#### Scenario: An example path is not a citation
- **WHEN** a path appears inside a fenced example block
- **THEN** it is not checked for existence

### Requirement: Each first gate is scoped to be passable when it lands

Every gate introduced by this change SHALL be introduced together with the scoping that makes it
passable against the state measured at introduction — a baseline, a restriction to touched artifacts,
or a warning-only mode — and that scoping SHALL be stated in the gate itself.

A gate that blocks every push on the day it arrives is removed or permanently skipped within a day,
and the rule it enforced ends up worse off than before, because the failed attempt is evidence
against trying again. Scoping is what converts a large existing violation count from a blocker into a
number that can be driven down.

#### Scenario: A gate lands without blocking existing work
- **WHEN** a gate is introduced against existing violations
- **THEN** a push that changes none of them passes

#### Scenario: The scoping is discoverable
- **WHEN** a reader opens a gate
- **THEN** the gate states how it is scoped and what would remove the scoping
