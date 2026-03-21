## ADDED Requirements

### Requirement: Rule suggestions section in LearningsPanel
The LearningsPanel SHALL include a "Rule Suggestions" section displaying rule candidates with Accept/Dismiss actions.

#### Scenario: Candidates present
- **WHEN** rule candidates exist for the project
- **THEN** the section SHALL display each candidate as an expandable card with title, classification badge, confidence level, occurrence count, and Accept/Dismiss buttons

#### Scenario: Candidate expanded
- **WHEN** the user expands a rule candidate card
- **THEN** the full suggested rule text SHALL be shown in a code block, along with the list of affected changes

#### Scenario: Accept clicked
- **WHEN** the user clicks Accept on a candidate
- **THEN** the web client SHALL call `POST /api/{project}/rule-candidates/{id}/action` with `action: "accept"` and show a success notification with the written file path

#### Scenario: Dismiss clicked
- **WHEN** the user clicks Dismiss on a candidate
- **THEN** the web client SHALL call the action endpoint with `action: "dismiss"` and remove the candidate from the list

#### Scenario: No candidates
- **WHEN** no rule candidates exist
- **THEN** the section SHALL show "No rule suggestions — run /set:learn after an orchestration run to analyze patterns"
