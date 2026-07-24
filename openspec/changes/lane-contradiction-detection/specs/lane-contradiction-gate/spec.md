## IN SCOPE
- Evaluating declared lane signals against the work a change actually delivered
- The difference between WARN and ENFORCE, and the measured condition for promotion
- Applying and maintaining a shrink-only baseline
- What the gate reports, and what it is forbidden from claiming

## OUT OF SCOPE
- Declaring signals (see `lane-signal-declaration`)
- Deciding a change's lane before work starts — no entrance classifier is specified
- Blocking a merge on anything other than an ENFORCE-level signal outside its baseline

## ADDED Requirements

### Requirement: The lane is measured after the work, never classified before it
The gate SHALL evaluate lane signals against the artefacts a change delivered. set-core
SHALL NOT introduce a step that asks any actor — human or agent — to classify a change's
lane before work begins, and SHALL NOT gate on the accuracy of such a classification.

Two lanes are differentiated by the *end of the process they gate*, not by a label chosen
at the start: a **changing** lane gates the entrance (is the right thing being built), a
**restoring** lane gates the exit (can the defect return). That asymmetry is the
behavioural difference between the pipelines, and it exists whether or not anyone declared
which lane they were in.

#### Scenario: A change declared trivial that delivers a new capability is caught
- **WHEN** a change's declared type selects a gate profile that skips review and softens
  spec verification
- **AND** a declared signal reports a new module delivered with no specification touched
- **THEN** the gate SHALL report the contradiction
- **AND** the report SHALL name the declared type and the contradicting artefact together,
  because either alone reads as normal

#### Scenario: No classification prompt is added anywhere
- **WHEN** the gate runs
- **THEN** it SHALL NOT invoke a model to determine a change's lane
- **AND** SHALL NOT require a new field on the change definition

### Requirement: A signal starts at WARN and is promoted only by its own measured condition
Every signal SHALL begin at WARN severity. A signal SHALL be promoted to ENFORCE only when
the measured condition declared alongside it is satisfied, and the promotion SHALL record
the measurement that justified it.

A signal with no satisfied promotion condition SHALL remain at WARN indefinitely rather
than being promoted by age, by hand, or by a global setting.

#### Scenario: A WARN signal does not block
- **WHEN** a WARN-severity signal fires on a change
- **THEN** the gate SHALL report it
- **AND** SHALL NOT fail the gate or block the merge

#### Scenario: Promotion without evidence is refused
- **WHEN** a project sets a signal to ENFORCE without recording the measurement its
  promotion condition names
- **THEN** set-core SHALL refuse the promotion and evaluate the signal at WARN
- **AND** SHALL report that the promotion was refused, rather than silently downgrading

### Requirement: A baseline records existing violations as debt and may only shrink
Each signal SHALL carry a baseline listing the violations that existed when it was
introduced. The gate SHALL NOT report a baselined violation. An entry SHALL be removable
from a baseline; the gate SHALL refuse any evaluation that would require adding one.

Without this, a signal introduced into a real repository fires on dozens of pre-existing
cases on its first day and is switched off within the week. The baseline is a debt
register, not forgiveness: it is the only place where the size of the backlog is visible,
and it is not permitted to grow.

#### Scenario: A pre-existing violation is silent, a new one is not
- **WHEN** a signal's baseline contains a violation, and a change introduces a second one
- **THEN** the gate SHALL report exactly the new violation
- **AND** the baselined one SHALL remain absent from the report

#### Scenario: A change that would grow the baseline fails
- **WHEN** a change adds a violation and also adds it to the baseline in the same change
- **THEN** the gate SHALL fail with an error naming baseline growth
- **AND** the failure SHALL be independent of the signal's WARN or ENFORCE severity

#### Scenario: The remaining debt is reported even when nothing new fired
- **WHEN** a change introduces no new violation and the baseline is non-empty
- **THEN** the gate SHALL report the count of baselined violations the project DECLARED,
  read from the declaration itself and not accumulated along the evaluation path
- **AND** SHALL report separately how many of them an evaluation actually reached
- **AND** SHALL NOT report the change as having no violations

#### Scenario: Debt that was never checked is not reported as no debt
- **WHEN** a signal declares baselined violations and no evaluation reaches them, because
  the signal is out of scope, its detector raised, or its condition could not be decided
- **THEN** the gate SHALL report the declared count as declared, and the unchecked count
  as unchecked
- **AND** SHALL NOT report a single debt figure of zero, because "there is no debt" and
  "the debt was not looked at" are opposite statements and one integer lets the
  reassuring one win

### Requirement: Every signal states its scope, and the gate evaluates only within it
The gate SHALL evaluate a signal only against work inside the signal's declared scope. A
signal SHALL NOT be evaluated on an integration path where the work it judges is already
merged history.

An unscoped signal re-evaluates work it has already judged, which produces noise
proportional to how long the project has existed and pressures the baseline upward — the
one direction the baseline may not move.

#### Scenario: A signal scoped to per-change verification does not run at merge time
- **WHEN** a signal declares its scope as per-change verification
- **AND** the merge queue runs integration gates on the accumulated result
- **THEN** the lane gate SHALL NOT evaluate that signal during the merge
- **AND** its absence there SHALL NOT be recorded as a pass

### Requirement: The gate reports what it could not decide, and never converts that into a pass
The gate's result SHALL distinguish three outcomes per signal: fired, did not fire, and
could not be evaluated. A signal that could not be evaluated SHALL NOT be counted toward a
passing result, and the gate SHALL NOT emit an overall verdict field asserting lane
correctness.

The gate can prove a contradiction; it cannot prove its absence. A change whose lane is
wrong in a way no declared signal covers passes it silently, and a summary verdict would
assert exactly what was never measured.

#### Scenario: An unevaluable signal is not a pass
- **WHEN** a signal's condition cannot be evaluated because the artefact it reads is absent
- **THEN** the gate SHALL report that signal as unevaluated, naming why
- **AND** SHALL NOT include it among the signals that did not fire

#### Scenario: No overall lane-correct verdict is emitted
- **WHEN** every declared signal is evaluated and none fires
- **THEN** the gate SHALL report the count of signals evaluated and the count unevaluated
- **AND** SHALL NOT emit a field asserting that the change's lane is correct
