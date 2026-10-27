# architecture-blueprint

## IN SCOPE

- The inputs the blueprint is built from, and the order they are read in
- The research document: one verdict per open question, sources, inference marking, the hands-on test
- The architecture blueprint document and its required sections
- Marking untested assumptions and tying them to the tests that gate the price
- The price-band check and how its result is presented
- The optional internal visual page built from the blueprint
- The handoff: commit scope and the report to the requester
- Delivery to consumer projects through the existing skill deploy

## OUT OF SCOPE

- Writing or pricing the client offer
- Extracting requirements from meetings automatically
- Provisioning, deploying or purchasing anything the blueprint describes
- Publishing or sharing the visual page beyond a private draft

## ADDED Requirements

### Requirement: The blueprint is built from written decisions first

The skill SHALL direct the agent to read the project's written internal decisions before
any other input, then the requirement list or previous offer, then meeting notes and
transcripts, and SHALL treat a conflict between a decision and an older source as resolved
in favour of the decision.

#### Scenario: Decisions read before transcripts
- **WHEN** an agent starts a blueprint and the project has an internal decisions document
- **THEN** the skill SHALL have the agent read that document before any meeting transcript
- **AND** the agent SHALL list each open question or test item from it as a research question

#### Scenario: No decisions document exists
- **WHEN** no written internal decisions are found
- **THEN** the skill SHALL have the agent ask the requester for them before writing the blueprint

### Requirement: Research gives one verdict per question, with sources

The research document SHALL answer each open question with exactly one verdict from the
fixed scale works / works with caveat / doesn't / unknown, SHALL give a URL for every factual
claim, SHALL mark every conclusion that no source states as an inference, SHALL record the
date the research was checked, and SHALL end each item with the hands-on test that still has
to be run.

#### Scenario: A claim without a source
- **WHEN** a research item states a conclusion that no cited page states
- **THEN** that conclusion SHALL be marked as an inference

#### Scenario: Each item ends with its test
- **WHEN** a research item is complete
- **THEN** it SHALL end with the hands-on test to run and what would count as passing

#### Scenario: Summary table
- **WHEN** the research document is written
- **THEN** it SHALL open with a table of every question, its verdict, and what it means for the design

### Requirement: The blueprint document carries the required sections

The architecture blueprint SHALL contain: the design in about five lines; a deployment
diagram of where each part runs; a placement table; a communication table naming, for each
link, the protocol, the authentication or key, where the key is stored and who can revoke
it; data ownership with one writer per table and the minimisation applied; a requirement to
component mapping covering every agreed requirement; failure modes and monitoring; security
with a sub-processor table naming role, region and legal basis whenever regulated or
personal data is processed; account ownership; an hours estimate per component with a low
and a high figure; a monthly running cost table; and the tests that gate the price with
pass criteria and fallbacks.

#### Scenario: Every agreed requirement is mapped
- **WHEN** the requirement mapping is written
- **THEN** every requirement from the decisions and the requirement list SHALL appear with a component, or be marked as a proposed cut or a placeholder

#### Scenario: Every key can be revoked
- **WHEN** a row of the communication table uses a key or token
- **THEN** the row SHALL name where it is stored and who can revoke it

#### Scenario: Accounts in the client's name
- **WHEN** the blueprint lists the accounts the solution needs
- **THEN** it SHALL state whose name each account is opened in and the exit path if the provider of the work leaves

### Requirement: Untested assumptions are visible and gate the price

Every statement in the blueprint that depends on something not yet tried SHALL be marked as
untested and SHALL reference the test that will settle it; the tests section SHALL list
which components each test gates, its pass criterion and its fallback.

#### Scenario: An assumption without a test
- **WHEN** the blueprint relies on an untested assumption
- **THEN** the assumption SHALL be marked and SHALL name a test id listed in the tests section

### Requirement: The price check presents options and does not choose

The skill SHALL have the agent compare the hours estimate with the stated price band and
day rate, state plainly whether the low and the high estimate fit, and, when they do not,
list concrete options such as a cap with named cuts or a split into phases, without
selecting one and without rewriting the plan around one.

#### Scenario: Estimate exceeds the band
- **WHEN** the high estimate costs more than the top of the price band
- **THEN** the blueprint SHALL state the gap in hours and money
- **AND** it SHALL list at least two options with their effect on hours
- **AND** it SHALL leave the choice to the requester

### Requirement: Running costs separate who pays and gross from net

The monthly cost table SHALL name who pays each item, SHALL state whether figures are gross
or net and why (for example the client's VAT status), SHALL state any currency conversion as
an assumption with its rate, and SHALL give the total the client actually pays.

#### Scenario: Foreign-currency subscription
- **WHEN** a cost is billed in another currency
- **THEN** the table SHALL show the converted figure and the assumed rate

### Requirement: The visual page is optional, internal and derived

When the requester asks for a visual version, the skill SHALL have the agent build it from
the blueprint document rather than from new claims, as a private page, following the host's
artifact rules, and SHALL keep internal-only content off any version meant for the client.

#### Scenario: Visual page requested
- **WHEN** the requester asks for a visual page of the blueprint
- **THEN** every figure on the page SHALL come from the committed blueprint or research document

### Requirement: The handoff is scoped and reports what changes the price

The skill SHALL have the agent commit only the blueprint and research files by explicit
path, and report to the requester the paths and the three to five findings that change the
price or the architecture.

#### Scenario: Commit with unrelated changes present
- **WHEN** the working tree holds changes the agent did not make
- **THEN** the commit SHALL include only the blueprint and research paths

### Requirement: The skill reaches consumers through the existing deploy

The skill and its templates SHALL live under `.claude/skills/set/blueprint/` and its command
under `.claude/commands/set/blueprint.md`, so that `set-project init` deploys them as new
files to a consumer without overwriting any consumer-owned file.

#### Scenario: Sources present
- **WHEN** the unit tests run
- **THEN** the skill file, both templates and the command file SHALL exist and carry the required sections
