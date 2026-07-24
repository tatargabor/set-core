## IN SCOPE
- A project declaring lane signals: the condition, the lane it belongs to, its scope, its
  baseline, and the measured condition under which it may be promoted from WARN to ENFORCE
- The rules Layer 1 obeys when reading those declarations
- What set-core does when a declaration is absent, partial, or malformed

## OUT OF SCOPE
- Evaluating a signal and producing a verdict (see `lane-contradiction-gate`)
- Choosing between differentiated pipelines — no router is specified anywhere
- `change_type`, gate profiles, and category resolution, which answer a different question
  (what a change touches) and are unchanged by this capability

## ADDED Requirements

### Requirement: set-core holds no lane signal of its own
Layer 1 SHALL contain no built-in lane signal, no default signal set, and no pattern
describing any project's file layout, defect store, or review artefacts. Every signal
SHALL come from a project's declaration.

The reason is the same one that keeps the status contract domain-free: a signal that ships
with the framework works for whoever it was written against and silently mismeasures
everyone else, while looking authoritative to both.

#### Scenario: A project declaring nothing gets today's behaviour
- **WHEN** a change is verified in a project that declares no lane signals
- **THEN** set-core SHALL evaluate no signal
- **AND** SHALL NOT report an all-clear, a zero-violation count, or a passing lane gate
- **AND** the gate's absence SHALL be distinguishable from a gate that ran and found nothing

#### Scenario: No signal is inferred from the framework's own conventions
- **WHEN** a project declares no signal but its tree contains `openspec/`, `tests/`, or any
  other structure set-core recognises
- **THEN** set-core SHALL NOT synthesise a signal from that structure

### Requirement: A signal declares a lane, a condition, a scope, a baseline and a promotion condition
A lane signal declaration SHALL carry all five fields. A declaration missing any of them
SHALL be refused with a named error, and the signal SHALL NOT be evaluated.

Refusal rather than a default is deliberate for each field: a defaulted scope evaluates
work the author never meant it to judge, a defaulted baseline forgives existing violations
silently, and a defaulted promotion condition turns a warning into a blocker without
anybody deciding it.

#### Scenario: A declaration missing its scope is refused
- **WHEN** a signal declares a condition, a lane, a baseline and a promotion condition, but
  no scope
- **THEN** set-core SHALL refuse the signal with an error naming the missing field
- **AND** SHALL NOT evaluate it against any change

#### Scenario: A refused signal does not silently disable the others
- **WHEN** one of three declared signals is refused as malformed
- **THEN** the remaining two SHALL still be evaluated
- **AND** the refusal SHALL be reported alongside their result, not in place of it

### Requirement: A signal's condition SHALL be mechanically decidable and SHALL NOT measure quantity
A lane signal's condition SHALL be evaluable from the delivered artefacts without a model,
a prompt, or a human judgement. A declaration whose condition is a threshold on lines
changed, files changed, or any other volume measure SHALL be refused.

Volume is the wrong axis and the failure is not marginal: a large generated update is
routine while a small change to a decision predicate on a critical path is not, so a size
threshold fires on exactly the wrong population. A signal SHALL instead name a **shape** —
a new module where none existed, a fixed defect with no test citing its identifier, a
completed task with no review artefact.

#### Scenario: A size threshold is refused
- **WHEN** a signal declares its condition as "more than 300 lines changed"
- **THEN** set-core SHALL refuse the signal with an error naming volume as the reason

#### Scenario: A shape condition is accepted
- **WHEN** a signal declares its condition as "a source file exists at a path matching the
  project's declared module pattern that did not exist before this change"
- **THEN** set-core SHALL accept the declaration

### Requirement: A signal SHALL NOT evaluate the corpus that defines it
Every declaration SHALL carry an exclusion covering the documents that define the signal —
its rule text, its specification, and its tests. set-core SHALL refuse a declaration whose
scope demonstrably includes its own definition.

This is not a nicety. A signal expressed as a pattern will match the sentence that
describes the pattern, so the gate reports its own documentation as a violation. The
cheapest way for anyone to silence it is then to delete the explanation of why it exists,
which removes the reason before the defect.

#### Scenario: A scope that swallows the rule that defines the signal is refused
- **WHEN** a signal's scope includes the path of the document declaring it
- **THEN** set-core SHALL refuse the declaration with an error naming self-inclusion

#### Scenario: Specification and test corpora are excluded by default in the declaration
- **WHEN** a project declares a signal without naming exclusions
- **THEN** the declaration SHALL be treated as incomplete under the five-field requirement
- **AND** SHALL NOT be evaluated

### Requirement: The declaration is read at evaluation time and never persisted
set-core SHALL read a project's lane signal declarations when it evaluates them and SHALL
NOT write them, their results, or any artefact derived from them into its own repository,
cache, or logs beyond what the run requires.

#### Scenario: A signal naming project-internal identifiers leaves no trace in the framework
- **WHEN** a signal's condition references a project's defect identifiers or path
  conventions
- **THEN** set-core SHALL evaluate it
- **AND** SHALL NOT persist those identifiers or conventions in any file under its own tree
