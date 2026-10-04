## IN SCOPE
- Rubric and threshold declared by the project
- Parsing the machine score marker
- The daily digest
- The reply-draft format and the copy-gate hook

## OUT OF SCOPE
- Any rubric, offer, voice or reference list shipped by set-core
- Sending a draft, which is a human's act
- Pricing or claims beyond what the project's draft template allows

## ADDED Requirements

### Requirement: Project-declared rubric
The rubric's dimensions, labels, maximum per dimension, guidance file and threshold SHALL come from the project's declaration, and set-core SHALL ship no default rubric.

#### Scenario: Declaration without a rubric
- **WHEN** `digest` runs and the declaration has no `rubric`
- **THEN** it SHALL fail validation and name the missing key

### Requirement: Score marker parsing
The score SHALL be read only from a whole-line `<!-- <marker>:score key=value ... -->` comment, where the marker name comes from the declaration. An item whose marker is missing, malformed, missing a dimension or out of range SHALL be reported as unscored and SHALL NOT count as zero.

#### Scenario: Out-of-range value
- **WHEN** a marker gives a dimension a value above its declared maximum
- **THEN** the item SHALL be listed as unscored, with the reason

#### Scenario: Marker inside a fenced example
- **WHEN** a score marker appears only inside a fenced code block
- **THEN** it SHALL NOT be read as the item's score

### Requirement: Threshold decides drafts
An item SHALL qualify for a reply draft exactly when its total meets `total_min` and every dimension listed in `dimension_min` meets its minimum.

#### Scenario: High total, low gating dimension
- **WHEN** an item totals above `total_min` but scores below the minimum on a gating dimension
- **THEN** it SHALL NOT qualify

### Requirement: Daily digest
`set-feed-watch digest <date>` SHALL write the declared digest file, listing that day's items by descending total, each with its one-line reason and links to the item and to its draft. It SHALL list a warning for every unscored item and for every qualifying item that has no draft.

#### Scenario: Missing draft
- **WHEN** a qualifying item has no draft file
- **THEN** the digest SHALL carry a warning line naming that item

### Requirement: Reply drafts are gated text a human sends
A reply draft SHALL put every outgoing text in a fenced block whose language is declared in `drafts.blocks`, and SHALL mark itself as a draft that a human sends. When `drafts.gate` is declared, `set-feed-watch gate <file>` SHALL run it over each declared block and the subject line, and SHALL exit non-zero if any run fails.

#### Scenario: Gate failure
- **WHEN** the declared gate rejects one block of a draft
- **THEN** `gate` SHALL exit non-zero and name the failing block

#### Scenario: No gate declared
- **WHEN** no `drafts.gate` is declared
- **THEN** `gate` SHALL report that no gate is configured, and SHALL NOT report a pass
