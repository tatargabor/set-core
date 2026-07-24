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

### Requirement: A signal declares a lane, a condition, a scope, a baseline, a promotion condition and a triggering case
A lane signal declaration SHALL carry all six fields. A declaration missing any of them
SHALL be refused with a named error, and the signal SHALL NOT be evaluated.

Refusal rather than a default is deliberate for each field: a defaulted scope evaluates
work the author never meant it to judge, a defaulted baseline forgives existing violations
silently, and a defaulted promotion condition turns a warning into a blocker without
anybody deciding it.

The **triggering case** — a date and an identifier for the incident the signal was written
in response to — is mandatory for a different reason, and it is the one field that would
normally be left to convention. A signal with no incident behind it is a guess dressed as a
rule, and there is no way to tell the two apart later.

**Only the dated identifier is machine-checked; the rationale is not, and this
specification SHALL NOT pretend otherwise.** Whether a paragraph actually explains anything
is not mechanically decidable — measured in a project running this pattern, two independent
proxies for "carries a rationale" both misclassified, in opposite directions. What a machine
can check is that a date and an identifier are present, and a line reading `# 2026-01-01`
satisfies that while explaining nothing. So the split is stated rather than blurred: the
**date and identifier are enforced by this gate**, the **explanation is enforced by review**.
A gate that implied otherwise would be a false gate of the kind this whole capability
exists to remove.

The same project's corrected figures, which are the reason the split is written down: 18 of
19 gates carry a rationale, 14 of 19 carry a dated case. The rationale is close to
universal; the *dating* is what is inconsistent, and it is also the only half a machine can
hold.

#### Scenario: A declaration missing its scope is refused
- **WHEN** a signal declares a condition, a lane, a baseline and a promotion condition, but
  no scope
- **THEN** set-core SHALL refuse the signal with an error naming the missing field
- **AND** SHALL NOT evaluate it against any change

#### Scenario: A refused signal does not silently disable the others
- **WHEN** one of three declared signals is refused as malformed
- **THEN** the remaining two SHALL still be evaluated
- **AND** the refusal SHALL be reported alongside their result, not in place of it

#### Scenario: A signal with no triggering case is refused
- **WHEN** a signal declares a lane, condition, scope, baseline and promotion condition but
  names no incident it was written in response to
- **THEN** set-core SHALL refuse the signal with an error naming the missing triggering case

#### Scenario: A dated identifier with no explanation is accepted, and the gate says so
- **WHEN** a signal's triggering case consists of a date and an identifier and nothing else
- **THEN** set-core SHALL accept the declaration
- **AND** SHALL NOT claim to have verified that the signal is justified
- **AND** the accepted-but-unexplained state SHALL be reported, so review has something to
  act on rather than a silent pass

### Requirement: The declaration lives in the tree being verified, not behind a running system
A lane signal declaration SHALL be readable from the checked-out tree alone. set-core SHALL
NOT obtain declarations by invoking a project's status contract, an HTTP endpoint, or
anything else requiring a running application or database.

Signals are evaluated during verification of a worktree, where there is no live project to
ask. A declaration reachable only through a running system is unreadable exactly when it is
needed, and a gate that cannot read its own configuration fails in the direction that looks
like "nothing to check".

#### Scenario: Declarations are read with no service running
- **WHEN** a change is verified in a worktree with no database and no application server
- **THEN** set-core SHALL read the project's declarations from the tree
- **AND** SHALL NOT attempt a contract command, an HTTP call, or a database connection

#### Scenario: Reading the declaration and evaluating the condition are different acts
- **WHEN** a signal's condition names an answer the project already publishes through its
  status contract
- **THEN** the prohibition above SHALL apply to reading the DECLARATION only
- **AND** evaluating the condition MAY invoke that project-declared command against the
  worktree being verified
- **AND** set-core SHALL NOT compute its own answer to a question the project publishes

### Requirement: The framework takes the project's published answer rather than recomputing it
Where a signal's condition names an answer the project already publishes, the gate SHALL
obtain the value by invoking that published command and SHALL NOT reimplement the
computation. set-core defines the SHAPE of a signal; the project supplies the VALUE.

Two implementations of one business value diverge silently. Measured on the consumer's side
before this was written: two paths computing the same figure drifted to 412% and 164%, and a
customer noticed before either side did. A framework-side reimplementation of a project's
own rule is that same defect with a longer feedback loop, because the two answers are read
by different people.

Invoking a published command is compatible with the requirement above because the worktree
being verified is not a live system: measured on a consumer's disposable worktree with no
`node_modules`, no `.env` and no database, their defect query answered in 129 ms — and,
crucially, answered about THAT tree: a reference broken only in the worktree changed the
worktree's answer and left the main tree's unchanged.

The delegated answer SHALL name a command and a **plain dotted path** to a list of violation
identifiers. set-core SHALL NOT accept an index, a filter, or a projection in that path, and
SHALL NOT accept a count in place of the list. A projection is the project's own rule
re-expressed in the framework's syntax, which is the second implementation this requirement
exists to prevent — the divergence it was written after needed two places, not two languages.
A count cannot be matched against the baseline and cannot be matched against the exclusions,
so it would report a figure nobody can act on or forgive.

A lane signal SHALL NOT invoke a command the project declares as a WRITE command, nor one its
contract does not declare as readable. This is enforced by the framework rather than trusted
to the declaration: the declaration is the project's, this guarantee is set-core's, and a gate
that mutated the tree it is judging is the worst place to discover the difference.

#### Scenario: A silent command is unevaluated, never a pass
- **WHEN** the published command fails, times out, or returns an unusable answer
- **THEN** the signal SHALL be reported as unevaluated with the reason
- **AND** SHALL NOT be reported as passing, and SHALL NOT fall back to a framework-side
  computation of the same value

#### Scenario: A tree that publishes nothing is distinguishable from a command that is broken
- **WHEN** the tree carries no status contract, or the command's entry point is absent from it
- **THEN** the signal SHALL be reported as unevaluated with a reason stating that THIS TREE
  DOES NOT PUBLISH the answer
- **AND** that state SHALL be distinguishable, in the gate's own output, from a command that
  is present and answered unusably
- **AND** neither state SHALL be reported as passing

The two are statements about different subjects — the checkout versus the change — and
merging them makes a project that never opted in report identically to one whose gate has
just died. Required by the consumer with a measurement behind it: their entire read
contract, every declared command and both signal declarations, existed on one machine and
was absent from the remote branch, so a clone or a CI run finds nothing to ask rather than
receiving a wrong answer.

A violation identifier SHALL be stable across environments. set-core SHALL NOT require a
particular identifier scheme — that is the project's — but a project publishing identifiers
its own tooling assigns at runtime SHALL expect the baseline and the exclusions to match on
one machine and not another, because both mechanisms key on the published string.

This is the same constraint the worktree requirement makes, one level down: the value is read
where no runtime exists, so an identifier that only a runtime can produce is not available at
the moment it is needed.

#### Scenario: A key aimed at a framework field is refused rather than stored
- **WHEN** a declaration carries a key that differs from an optional framework field only by
  prefix, suffix, plural, case, or separator
- **THEN** set-core SHALL refuse the declaration, naming both the declared key and the field
  it resembles
- **AND** SHALL NOT store it as an uninterpreted field

Reporting it as unread is not sufficient here, and the difference is the point: an unread
report is a report, whereas a missed delegation key silently selects the framework-side
route — the recomputation the delegation exists to prevent. The same miss on the blocking
flag reads as `false`, so a signal its project declared the only enforcement of its class
stops blocking and nothing says so. Required fields are deliberately excluded: a typo there
leaves the real field missing, which is already refused by name.

#### Scenario: A projection in the declared path is refused
- **WHEN** a signal's delegated answer names a path containing an index, a wildcard or a
  filter
- **THEN** set-core SHALL refuse the declaration, naming the reason
- **AND** the project SHALL instead publish the decided list under one path

#### Scenario: A published count is not a published answer
- **WHEN** the declared path holds a number rather than a list of identifiers
- **THEN** the signal SHALL be reported as unevaluated with the reason
- **AND** SHALL NOT be reported as passing when that number is zero

#### Scenario: A signal that is the only enforcement of its defect class blocks instead of falling silent
- **WHEN** a signal's declaration states that no other gate enforces its defect class
- **THEN** an unevaluable signal SHALL block rather than report silence
- **AND** the gate SHALL name the missing answer as the reason
- **AND** this SHALL apply whether the answer was unusable or the tree publishes none —
  naming the state honestly and refusing to pass are not in tension

#### Scenario: Out-of-scope silence is not a hole and does not block
- **WHEN** a signal declaring itself the sole enforcement of its class is reached in a phase
  it was not declared for
- **THEN** it SHALL NOT block
- **AND** its absence there SHALL still be recorded as not evaluated

A signal declared for per-change verification is not unenforced at merge time; it runs in its
own phase. Blocking there would fail every integration run, which is how a gate is switched
off in its first week — taking the warning with it.

This condition was required by the consumer as the price of accepting the previous scenario,
and it is the honest limit of it: their agreement holds *because their own blocking gate
covers the same defect class*, so a silent framework signal costs earlier warning and not
protection. Where that is not true, silence is a real hole and the reassuring direction wins
again.

### Requirement: The triggering case appears in the gate's own message, not only in the specification
When a signal fires, the reported message SHALL carry the signal's triggering case. It SHALL
NOT be sufficient for that case to exist only in the declaration file or in this
specification.

The person reading a gate's output is reading it *because it just fired*, and that is the
only moment the reason is worth anything. If the rationale lives one indirection away, the
fastest available response is to suppress the gate — so a signal that cannot explain itself
at the point of firing trains people to switch it off.

#### Scenario: A firing signal states why it exists
- **WHEN** a signal fires on a change
- **THEN** the reported message SHALL include the date and identifier of the incident the
  signal was written for
- **AND** SHALL include the way to suppress this one signal, rather than leaving a blanket
  bypass as the reader's only discoverable option

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
