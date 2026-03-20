# secret-code-enumeration

Delta spec for `.claude/rules/web/security-patterns.md`.

## ADDED Requirements

### Requirement: Secret code enumeration prevention

Endpoints accepting secret codes (gift cards, coupons, invite codes, password reset tokens, activation codes) MUST return a single generic error message for all failure cases. The response SHALL NOT distinguish between "code not found", "code expired", "code already used", or "code belongs to another user". Distinct error messages allow attackers to enumerate valid codes and determine their state.

#### Scenario: Invalid gift card code submitted

- **WHEN** a user submits a gift card code that does not exist in the database
- **THEN** the API returns a generic error (e.g., "Invalid or expired code") identical to the response for expired or already-used codes

#### Scenario: Expired coupon code submitted

- **WHEN** a user submits a coupon code that exists but has expired
- **THEN** the API returns the same generic error as for non-existent codes — never "This coupon has expired"

#### Scenario: Already-used invite code submitted

- **WHEN** a user submits an invite code that has already been redeemed
- **THEN** the API returns the same generic error — never "This invite has already been used"

#### Scenario: Rate limiting on code validation endpoints

- **WHEN** a client sends more than a threshold number of code validation requests in a time window
- **THEN** the endpoint applies rate limiting to prevent brute-force enumeration attempts
