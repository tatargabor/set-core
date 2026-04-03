## MODIFIED Requirements

### Requirement: Session cookie extraction
The system SHALL extract the `sessionKey` cookie for `claude.ai` from each Chrome profile's cookie database AND validate that the session is still active by checking the HTTP response status from the Claude API.

#### Scenario: Session cookie found and validated
- **WHEN** a Chrome profile has a `sessionKey` cookie for `.claude.ai`
- **AND** the Claude organizations API returns HTTP 200 with valid JSON
- **THEN** the scanner SHALL include the session in results with the resolved org name

#### Scenario: Session cookie found but expired
- **WHEN** a Chrome profile has a `sessionKey` cookie for `.claude.ai`
- **AND** the Claude organizations API returns HTTP 401 or 403
- **THEN** the scanner SHALL exclude that session from results
- **AND** log a debug message indicating the session is expired

#### Scenario: Session cookie found but validation inconclusive
- **WHEN** a Chrome profile has a `sessionKey` cookie for `.claude.ai`
- **AND** the Claude organizations API call fails due to network error, timeout, or non-auth HTTP error
- **THEN** the scanner SHALL include the session in results
- **AND** the session SHALL be marked with `"verified": false`
- **AND** the name SHALL fall back to Chrome profile name resolution

#### Scenario: No session cookie in profile
- **WHEN** a Chrome profile does not have a `sessionKey` cookie for `claude.ai`
- **THEN** that profile SHALL be skipped (not included in results)

#### Scenario: Cookie decryption fails
- **WHEN** cookie decryption fails for a profile (keyring locked, permissions, etc.)
- **THEN** that profile SHALL be skipped
- **AND** the error SHALL be logged but not shown to the user

## ADDED Requirements

### Requirement: Structured session validation
The system SHALL provide a validation function that returns both the session status and org name in a single API call, distinguishing between expired, valid, and inconclusive states.

#### Scenario: Valid session returns org name
- **WHEN** `_validate_session(session_key)` is called with a valid session key
- **AND** the organizations API returns HTTP 200 with a non-empty org list
- **THEN** the function SHALL return `("valid", "<org_name>")`

#### Scenario: Expired session detected via 401
- **WHEN** `_validate_session(session_key)` is called
- **AND** the organizations API returns HTTP 401 or 403
- **THEN** the function SHALL return `("expired", None)`

#### Scenario: Expired session detected via empty response
- **WHEN** `_validate_session(session_key)` is called
- **AND** the organizations API returns HTTP 200 but the response is not a valid org list (empty list, HTML login page, error JSON)
- **THEN** the function SHALL return `("expired", None)`

#### Scenario: Network error returns inconclusive
- **WHEN** `_validate_session(session_key)` is called
- **AND** the API call fails due to timeout, DNS failure, connection refused, or other network error
- **THEN** the function SHALL return `("error", None)`

#### Scenario: Fallback chain for validation
- **WHEN** the primary HTTP client (curl_cffi) fails with a network error
- **THEN** the system SHALL try the curl subprocess fallback
- **AND** if both fail, return `("error", None)`
- **AND** the status SHALL reflect the most definitive result (if any attempt returns 401/403, the result is "expired" regardless of other attempts)
