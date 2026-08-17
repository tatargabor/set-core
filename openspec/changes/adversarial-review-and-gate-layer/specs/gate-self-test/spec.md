## IN SCOPE
- The self-test every gate must carry, and what makes it two-directional
- The gate that enforces the existence of those self-tests
- Where the fixtures a self-test runs against may live

## OUT OF SCOPE
- What any individual gate checks
- Testing the framework's runtime or the orchestration engine's integration gates

## ADDED Requirements

### Requirement: Every gate carries a two-directional self-test

Every gate SHALL have a self-test that runs it against a fixture violating the rule, asserting that
it fails, and against a clean fixture, asserting that it passes. A self-test asserting only one
direction SHALL NOT satisfy this requirement.

A gate that cannot fail is indistinguishable from a gate that is not installed, and the failure is
silent and reassuring: pushes pass, the number stays at zero, and the rule looks enforced. The
adopted implementation shipped exactly this defect — its check matched one shape of finding while
some documents used another, so a change whose own header declared implementation blocked passed the
gate and was archived. A one-directional test would have passed on that build.

#### Scenario: The gate fires on the violation
- **WHEN** the self-test runs the gate against a fixture that violates the rule
- **THEN** the gate fails

#### Scenario: The gate is silent on a clean case
- **WHEN** the self-test runs the gate against a fixture that does not violate the rule
- **THEN** the gate passes

#### Scenario: A one-directional test is not enough
- **WHEN** a gate's self-test asserts only that it passes on clean input
- **THEN** the self-test is incomplete and the gate counts as untested

### Requirement: A gate without a self-test is itself a gate failure

The layer SHALL check that every gate present has a self-test, and SHALL fail when one does not.

Without this, the self-test requirement is a convention, and a convention decays exactly where it
matters — a gate added in a hurry, to enforce something urgent, is the one most likely to ship
untested and the one whose silence is most expensive.

#### Scenario: A new gate without a self-test is caught
- **WHEN** a gate exists with no corresponding self-test
- **THEN** the meta-check fails and names the gate

#### Scenario: The meta-check tests itself too
- **WHEN** the meta-check runs
- **THEN** it is subject to the same two-directional requirement as any other gate

### Requirement: Self-test fixtures live outside the repository being checked

A self-test SHALL run its gate against fixtures created outside this repository's working tree.

A gate under test must not be measuring the tree that contains its own fixtures: a violating fixture
committed into this repository would make the gate fail on every real push, and one placed in an
ignored directory would make the *result* depend on ignore rules rather than on the gate. This is the
measurement-inside-the-corpus class, which has already produced repeated wrong readings in this
project.

#### Scenario: A violating fixture does not break real pushes
- **WHEN** a self-test needs a fixture that violates the rule
- **THEN** the fixture is created outside the working tree and removed afterwards

#### Scenario: The gate is run against the fixture, not against the repository
- **WHEN** a self-test runs
- **THEN** the gate's target is the fixture tree, and the result does not depend on this repository's
  current state
