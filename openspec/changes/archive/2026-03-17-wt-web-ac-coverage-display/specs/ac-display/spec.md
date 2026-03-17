## ADDED Requirements

## IN SCOPE
- Display acceptance criteria items inline in requirement tables (DigestView + ProgressView)
- Cross-cutting AC Coverage sub-tab in DigestView with domain grouping and progress tracking
- Expandable requirement rows showing AC items as a checklist
- AC checked state derived from change status (merged = checked) — simple mode

## OUT OF SCOPE
- Per-AC pass/fail from verifier review output parsing (rich mode — future change)
- Backend modifications to digest.py or verifier.py (already done)
- AC editing or manual check/uncheck from the UI

### Requirement: DigestReq type includes acceptance_criteria
The frontend `DigestReq` TypeScript interface SHALL include an `acceptance_criteria` field of type `string[]`. When the field is absent or null in the API response, consumers SHALL default to an empty array.

#### Scenario: AC field present in digest response
- **WHEN** the digest API returns a requirement with `acceptance_criteria: ["POST /cart → 201", "Cart badge updates"]`
- **THEN** the frontend DigestReq object SHALL have `acceptance_criteria` populated with those strings

#### Scenario: AC field missing (old digest)
- **WHEN** the digest API returns a requirement without `acceptance_criteria`
- **THEN** the frontend SHALL treat it as `acceptance_criteria: []` with no error

### Requirement: Inline AC display in requirement tables
Both DigestView (Requirements panel) and ProgressView (DigestFallbackView) SHALL render AC items when a requirement row is expanded. Each AC item SHALL display as a checkbox-style line.

#### Scenario: Expand requirement with AC items
- **WHEN** user clicks/expands a requirement row that has 3 acceptance criteria
- **THEN** 3 AC items render below the row, each prefixed with a check indicator
- **AND** items where the associated change status is merged/done/completed show as checked
- **AND** items where the change is not done show as unchecked

#### Scenario: Requirement with no AC items
- **WHEN** user expands a requirement row with empty acceptance_criteria
- **THEN** no AC section renders (no empty state message needed)

#### Scenario: AC display in ProgressView digest fallback
- **WHEN** the ProgressView falls back to digest requirements (no plan data)
- **THEN** the requirement rows SHALL also support expanding to show AC items

### Requirement: AC Coverage sub-tab in DigestView
DigestView SHALL include an additional sub-tab labeled "AC" (after the existing overview/requirements/domains/triage tabs). This tab SHALL show a cross-cutting view of all acceptance criteria across all requirements.

#### Scenario: AC tab shows aggregate progress
- **WHEN** user navigates to the AC sub-tab
- **THEN** a progress bar shows total checked AC / total AC count
- **AND** requirements are grouped by domain
- **AND** each AC item shows its requirement ID, the AC text, and checked/unchecked state

#### Scenario: AC tab with no AC data
- **WHEN** all requirements have empty acceptance_criteria
- **THEN** the AC tab SHALL show "No acceptance criteria extracted" message

#### Scenario: Filter by domain
- **WHEN** user is on the AC tab
- **THEN** a domain filter dropdown allows filtering to a single domain
