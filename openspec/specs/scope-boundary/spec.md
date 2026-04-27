# Scope Boundary Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Spec template includes scope boundary section
The spec artifact template SHALL include an optional IN SCOPE / OUT OF SCOPE section after the Purpose/preamble and before Requirements. This section declares what the capability covers and what it explicitly excludes.

#### Scenario: New spec created with scope boundary
- **WHEN** an agent creates a spec file using `openspec instructions specs`
- **THEN** the template SHALL include an IN SCOPE / OUT OF SCOPE section
- **AND** the instruction SHALL guide the agent to list included and excluded functionality as bullet points

#### Scenario: Existing spec without scope boundary
- **WHEN** the verify skill processes a spec that lacks IN SCOPE / OUT OF SCOPE sections
- **THEN** the verify skill SHALL skip scope boundary checking for that spec
- **AND** the verify skill SHALL note "No scope boundary defined — skipping overshoot check"

### Requirement: Verify skill enforces scope boundary
The verify-change skill SHALL read the IN SCOPE section and check that implementation stays within declared scope. It SHALL read the OUT OF SCOPE section and flag any implementation that matches excluded items.

#### Scenario: Implementation within scope
- **WHEN** the verify skill finds implementation evidence for items listed in IN SCOPE
- **THEN** those items SHALL be marked as covered in the verification report

#### Scenario: Implementation matches OUT OF SCOPE item
- **WHEN** the verify skill detects implementation of something listed in OUT OF SCOPE
- **THEN** it SHALL report a WARNING: "Out-of-scope implementation detected: <item>"
- **AND** the recommendation SHALL be: "Remove <item> or update spec scope boundary"

#### Scenario: Agent prompt includes scope constraint
- **WHEN** an agent reads a spec with IN SCOPE / OUT OF SCOPE sections during apply
- **THEN** the apply skill instruction SHALL direct the agent to implement ONLY items in IN SCOPE
- **AND** the instruction SHALL explicitly state: "Do NOT implement items listed in OUT OF SCOPE"
