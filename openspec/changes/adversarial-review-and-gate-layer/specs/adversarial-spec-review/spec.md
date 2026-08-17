## IN SCOPE
- When a change's plan must be reviewed adversarially, and when it need not be
- The two independent review branches and what each one is responsible for
- The findings artifact: its severities, its per-finding status, and its mandatory closing section
- What a finding must carry before it counts as a finding

## OUT OF SCOPE
- Enforcing the review mechanically (`repo-gate-layer`, `rule-enforcement-gates`)
- Verifying an implementation after it is written — a different step, already covered
- Deciding a business or architectural branch that the review surfaces; that belongs to the user

## ADDED Requirements

### Requirement: A change with code impact is reviewed adversarially before implementation begins

A change whose implementation touches code SHALL be reviewed adversarially after its planning
artifacts exist and before implementation starts, and the review's result SHALL be recorded as an
artifact in the change directory. A pure documentation change, or a mechanical single-line fix with
no planning artifacts, SHALL NOT require one.

Internal consistency is not fit. A plan can be internally coherent, pass every structural validation,
and still be wrong about the code it plans to change — measured on a consumer project, where a change
built from a code map, a measured spike and ten delta specs, validating cleanly, was found by review
to delete a route another feature depended on and to reproduce the very defect it was written to fix.
Neither was visible from the plan.

#### Scenario: A code-affecting change is reviewed before apply
- **WHEN** a change's planning artifacts are complete and its implementation would touch code
- **THEN** the adversarial review runs and its findings artifact exists before any task is started

#### Scenario: A documentation-only change is exempt
- **WHEN** a change has no code impact
- **THEN** no review is required, and the exemption is a stated property of the change rather than an
  omission

#### Scenario: Validation passing is not a substitute
- **WHEN** a change validates cleanly against its schema
- **THEN** the review is still required, because validation measures structure and not fit

### Requirement: The review runs as two independent branches

The review SHALL consist of two branches that run independently of one another: one that attacks the
plan against the real source code, and one that checks the plan against the project's mandatory
rules. A single combined reviewer SHALL NOT satisfy this requirement.

The two branches find different defect classes and neither finds the other's. The code branch finds
lost call sites, race conditions, deleted entry points and collisions with other active changes; the
rules branch finds a missing traceability tag, an unregistered scheduled job, or a requirement
written as added where it modifies an existing one. A single reviewer asked to do both does whichever
is easier and reports it as both.

#### Scenario: Both branches produce findings
- **WHEN** the review runs
- **THEN** both branches contribute to the findings artifact, each identifiable

#### Scenario: One branch finding nothing does not excuse the other
- **WHEN** one branch reports no findings
- **THEN** the other branch still runs and still records what it checked

### Requirement: The code branch reads the source, and every claim carries evidence

The branch that reviews against code SHALL derive its findings from the source rather than from the
change's own artifacts, and every finding SHALL carry a `file:line` reference, a one-sentence claim,
a failure scenario stating concrete input and the wrong output it produces, and a severity.

A finding without a failure scenario cannot be argued with, cannot be prioritised and cannot be shown
to be resolved. A finding without a source reference is an opinion about a plan, which is what this
branch exists to replace.

#### Scenario: A finding carries its evidence
- **WHEN** the code branch reports a defect
- **THEN** it names the source location, the input that triggers it, and the wrong result

#### Scenario: A plan-only observation is not a code finding
- **WHEN** an observation can be made without reading the source
- **THEN** it does not belong to this branch's findings

### Requirement: An empty result is stated, never manufactured

Each branch SHALL state explicitly when it found no genuine defect, and SHALL NOT report a finding it
does not believe. Each branch SHALL also close with an itemised statement of what it checked and
found correct.

Both halves guard the same failure. An agent asked to be adversarial and finding nothing will invent
something to appear useful, and a false finding costs a real plan change. And without the closing
section, "found nothing" and "did not look there" produce identical output — the reader cannot tell
coverage from silence, which is the gap-is-not-a-zero rule applied to a review.

#### Scenario: Nothing found is said plainly
- **WHEN** a branch finds no genuine defect
- **THEN** it says so, and does not report a finding to fill the space

#### Scenario: Coverage is stated
- **WHEN** a branch completes
- **THEN** it lists what it examined and found correct, itemised rather than summarised

### Requirement: Findings carry a severity and a status, and a critical finding blocks

Every finding SHALL carry a severity and a status. A finding at the highest severity SHALL block
implementation until its status records that it was carried into the change's artifacts or that it
was deliberately rejected with a stated reason. A finding that raises a business or architectural
branch SHALL be recorded as a decision for the user rather than settled by the reviewer.

Rejection with a reason is a legitimate outcome and must stay cheap; silently ignoring a finding must
not be possible. The distinction between the two is the status field, which is why it is mandatory
rather than conventional.

#### Scenario: An unresolved critical finding blocks
- **WHEN** a critical finding's status is still open
- **THEN** implementation of that change is blocked

#### Scenario: A rejected finding unblocks with its reason
- **WHEN** a critical finding is rejected with a stated reason
- **THEN** it no longer blocks, and the reason remains in the artifact

#### Scenario: A branch for the user is not decided by the reviewer
- **WHEN** a finding presents a choice between two legitimate designs
- **THEN** it is recorded as an open decision for the user, not resolved in the findings
