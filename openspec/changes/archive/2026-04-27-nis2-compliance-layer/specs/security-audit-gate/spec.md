# Spec: Security Audit Gate

## ADDED Requirements

## IN SCOPE
- Dedicated `security-audit` gate registered via `WebProjectType.register_gates()`
- Gate executor running: npm audit (dependency vulnerabilities), security header scan, weak crypto pattern scan
- Gate position in pipeline: after `test`, before `review`
- Change-type aware defaults (foundational/feature: run, cleanup: soft)
- Retry context with actionable fix messages
- Conditional activation via `compliance.nis2.enabled` config

## OUT OF SCOPE
- DAST (dynamic application security testing) against running application
- SBOM file generation (future capability)
- Container image scanning
- IaC policy validation
- Integration with external SAST tools (CodeQL, Semgrep, SonarQube)
- License compliance checking

### Requirement: Security audit gate registration
The system SHALL register a `security-audit` gate in `WebProjectType.register_gates()` when NIS2 compliance is enabled. The gate SHALL have position `after:test` (runs after unit tests, before code review). It SHALL use its own retry counter `security_retry_count`.

#### Scenario: Gate appears in pipeline
- **WHEN** NIS2 is enabled and gate pipeline is constructed
- **THEN** the gate list includes `security-audit` between `test` and `review`

#### Scenario: Gate absent when NIS2 disabled
- **WHEN** NIS2 is not enabled
- **THEN** `register_gates()` does not include `security-audit`

### Requirement: Dependency audit check
The gate executor SHALL run `npm audit --json` (or equivalent for detected package manager) and parse the output. If any vulnerability with severity `high` or `critical` is found, the check fails. The retry context SHALL include the package name, vulnerability ID, and suggested fix (e.g., `npm audit fix` or specific version upgrade).

#### Scenario: No high vulnerabilities
- **WHEN** `npm audit` reports only low/moderate findings
- **THEN** the dependency audit check passes

#### Scenario: Critical vulnerability found
- **WHEN** `npm audit` reports a critical vulnerability in `lodash@4.17.20`
- **THEN** the check fails with retry context: package name, CVE ID, recommended version

### Requirement: Security header validation
The gate executor SHALL scan `next.config.js` (or `next.config.mjs`/`next.config.ts`) for security header configuration. Required headers: `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`. Missing headers are reported as warnings (non-blocking) with fix instructions.

#### Scenario: All headers present
- **WHEN** `next.config.js` exports headers with X-Frame-Options, X-Content-Type-Options, and HSTS
- **THEN** the header validation passes with no warnings

#### Scenario: Missing HSTS header
- **WHEN** `next.config.js` has X-Frame-Options but not Strict-Transport-Security
- **THEN** the check passes (non-blocking) with a warning listing the missing header and example config

### Requirement: Crypto pattern scan
The gate executor SHALL scan all `.ts` and `.tsx` files for weak cryptographic patterns: MD5 usage, SHA1 usage, `Math.random()` for security values. Any finding is a gate failure (blocking). Retry context SHALL include file path, line number, and recommended replacement (e.g., `crypto.randomUUID()` instead of `Math.random()`).

#### Scenario: Weak crypto detected
- **WHEN** `src/lib/tokens.ts` contains `Math.random().toString(36)` for token generation
- **THEN** the gate fails with retry context pointing to the file/line and suggesting `crypto.randomUUID()`

#### Scenario: Strong crypto only
- **WHEN** all source files use `crypto.randomUUID()` or `crypto.randomBytes()`
- **THEN** the crypto pattern scan passes

### Requirement: Gate result reporting
The gate SHALL produce a structured result with fields: `security_result` (pass/fail/warn), `gate_security_ms` (execution time), and a `details` section listing each sub-check result. On failure, the retry context SHALL be a formatted markdown block suitable for agent consumption.

#### Scenario: Gate passes with warnings
- **WHEN** dep audit passes, headers have warnings, crypto passes
- **THEN** `security_result` is "warn", gate does not block merge, warnings logged

#### Scenario: Gate fails
- **WHEN** dep audit finds critical vulnerability
- **THEN** `security_result` is "fail", merge blocked, retry context includes fix instructions

### Requirement: Change-type aware defaults
The gate SHALL have the following defaults per change type:
- `foundational`: run (blocking)
- `schema`: run (blocking)
- `feature`: run (blocking)
- `cleanup-before`: soft (non-blocking)
- `cleanup-after`: soft (non-blocking)

#### Scenario: Cleanup change skips blocking
- **WHEN** a `cleanup-after` change runs through the gate pipeline
- **THEN** the security-audit gate runs in `soft` mode (findings logged, never blocks merge)
