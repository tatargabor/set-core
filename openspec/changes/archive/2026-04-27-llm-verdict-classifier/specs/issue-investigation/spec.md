## ADDED Requirements

### Requirement: Investigator diagnosis uses sentinels then classifier fallback
The `IssueInvestigator._parse_proposal` method SHALL prefer explicit sentinels in the proposal.md for `**Impact:**`, `**Fix-Scope:**`, `**Target:**`, and `**Confidence:**` fields. When a sentinel is absent for a given field, the parser SHALL invoke the LLM verdict classifier on the proposal content instead of falling back to keyword heuristics on the raw body text.

#### Scenario: All sentinels present, classifier skipped
- **GIVEN** a proposal.md containing `**Impact:** high`, `**Fix-Scope:** config_override`, `**Target:** framework`, `**Confidence:** 90`
- **WHEN** `_parse_proposal` runs
- **THEN** the returned Diagnosis has `impact="high"`, `fix_scope="config_override"`, `fix_target="framework"`, `confidence=0.9`
- **AND** the classifier is NOT invoked

#### Scenario: Missing sentinels filled by classifier
- **GIVEN** a proposal.md with free-form markdown and no `**Impact:**` sentinel
- **AND** the directive `llm_verdict_classifier_enabled` is True
- **WHEN** `_parse_proposal` runs
- **THEN** the classifier is invoked with an investigator schema
- **AND** the classifier-reported impact populates the Diagnosis
- **AND** the keyword heuristic path is NOT used

#### Scenario: Classifier error falls through to keyword heuristic
- **GIVEN** a proposal.md with missing sentinels
- **AND** the classifier Sonnet call fails (timeout or non-zero exit)
- **WHEN** `_parse_proposal` runs
- **THEN** the parser falls back to the old keyword heuristic (`"critical" in lines` etc.)
- **AND** a WARNING log line notes that the classifier failed and the heuristic is being used as a last resort
- **AND** the `Diagnosis.confidence` is reduced by 0.1 to reflect the degraded extraction path

### Requirement: Investigator keyword heuristics no longer trigger on word-substring matches
The investigator's keyword heuristic fallback SHALL use word-boundary matching, not substring matching, so that words like "criticality" or "not critical" do not trigger an `impact="high"` classification.

#### Scenario: Word "criticality" does not trigger critical impact
- **GIVEN** a proposal.md body that uses the phrase "reviewed for criticality"
- **AND** the classifier is disabled or has failed
- **WHEN** the keyword heuristic runs
- **THEN** the Diagnosis does NOT have `impact="high"` from the substring match on "critical"
