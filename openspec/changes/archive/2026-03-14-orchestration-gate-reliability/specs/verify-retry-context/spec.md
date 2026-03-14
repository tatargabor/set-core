## MODIFIED Requirements

### Requirement: Verify retry context includes gate identity
When a verify gate fails and triggers retry, the retry_context SHALL identify which specific gate failed and include the relevant output.

#### Scenario: Verify sentinel missing triggers retry
- **WHEN** the verify gate fails due to missing sentinel line
- **THEN** retry_context SHALL explicitly instruct the agent to re-run `/opsx:verify` and ensure output ends with the `VERIFY_RESULT:` sentinel line
