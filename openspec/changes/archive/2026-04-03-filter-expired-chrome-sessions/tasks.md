# Tasks: Filter Expired Chrome Sessions

## 1. Refactor org fetch to session validation

- [x] 1.1 Create `_validate_session(session_key)` function that returns `tuple[str, str | None]` with status `"valid"`, `"expired"`, or `"error"` [REQ: structured-session-validation]
- [x] 1.2 In curl_cffi path: check `resp.status_code` for 401/403 before JSON parse — return `("expired", None)` on auth errors [REQ: structured-session-validation]
- [x] 1.3 In curl_cffi path: on HTTP 200, validate response is a non-empty org list — return `("expired", None)` if body is HTML or empty list [REQ: structured-session-validation]
- [x] 1.4 In curl subprocess fallback: extract HTTP status code via `-w '%{http_code}'` and apply same auth error logic [REQ: structured-session-validation]
- [x] 1.5 Return `("error", None)` for network failures (timeout, DNS, connection refused) [REQ: structured-session-validation]
- [x] 1.6 Remove old `_fetch_org_name()` function [REQ: structured-session-validation]

## 2. Update scan to filter based on validation

- [x] 2.1 Replace `_fetch_org_name()` call in `scan_chrome_sessions()` with `_validate_session()` [REQ: session-cookie-extraction]
- [x] 2.2 Exclude sessions where validation returns `"expired"` [REQ: session-cookie-extraction]
- [x] 2.3 Include sessions where validation returns `"error"` with `verified=False` and profile name fallback [REQ: session-cookie-extraction]
- [x] 2.4 Include sessions where validation returns `"valid"` with org name [REQ: session-cookie-extraction]
- [x] 2.5 Update cache logic to work with new `_validate_session()` return type [REQ: session-cookie-extraction]

## 3. Tests

- [x] 3.1 Test `_validate_session()` returns `("valid", org_name)` on HTTP 200 with valid org list [REQ: structured-session-validation]
- [x] 3.2 Test `_validate_session()` returns `("expired", None)` on HTTP 401/403 [REQ: structured-session-validation]
- [x] 3.3 Test `_validate_session()` returns `("expired", None)` on HTTP 200 with empty/invalid response [REQ: structured-session-validation]
- [x] 3.4 Test `_validate_session()` returns `("error", None)` on network failure [REQ: structured-session-validation]
- [x] 3.5 Test `scan_chrome_sessions()` excludes expired sessions from results [REQ: session-cookie-extraction]
- [x] 3.6 Test `scan_chrome_sessions()` includes unverified sessions with `verified=False` [REQ: session-cookie-extraction]
- [x] 3.7 Update existing tests that mock `_fetch_org_name` to use `_validate_session` [REQ: session-cookie-extraction]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN organizations API returns HTTP 200 with valid org list THEN return `("valid", org_name)` [REQ: structured-session-validation, scenario: valid-session-returns-org-name]
- [x] AC-2: WHEN organizations API returns HTTP 401 or 403 THEN return `("expired", None)` [REQ: structured-session-validation, scenario: expired-session-detected-via-401]
- [x] AC-3: WHEN organizations API returns HTTP 200 but invalid body THEN return `("expired", None)` [REQ: structured-session-validation, scenario: expired-session-detected-via-empty-response]
- [x] AC-4: WHEN API call fails due to network error THEN return `("error", None)` [REQ: structured-session-validation, scenario: network-error-returns-inconclusive]
- [x] AC-5: WHEN session is expired THEN scanner excludes it from results [REQ: session-cookie-extraction, scenario: session-cookie-found-but-expired]
- [x] AC-6: WHEN validation is inconclusive THEN scanner includes session with `verified=false` [REQ: session-cookie-extraction, scenario: session-cookie-found-but-validation-inconclusive]
