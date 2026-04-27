# Spec: NIS2 Compliance Rules

## ADDED Requirements

## IN SCOPE
- Template rule files deployed to consumer projects via `set-project init` (security-nis2.md, logging-audit.md, supply-chain.md)
- Verification rules added to `WebProjectType` for NIS2 compliance checks
- Forbidden patterns for security anti-patterns
- Opt-in activation via `compliance.nis2.enabled` config flag
- All rules conditional — inactive by default, zero impact on non-NIS2 projects

## OUT OF SCOPE
- Runtime enforcement (WAF, SIEM integration, real-time monitoring)
- Organizational policies (HR security, physical access, training programs)
- Certificate management or PKI infrastructure
- SBOM generation tooling (may be added later as separate capability)
- Incident response workflow automation
- External audit report generation

### Requirement: NIS2 template rules deployment
The system SHALL deploy three NIS2-specific rule files to consumer projects when `compliance.nis2.enabled` is true in `set/orchestration/config.yaml`. Files: `security-nis2.md` (Article 21 coding patterns), `logging-audit.md` (structured audit trail patterns), `supply-chain.md` (dependency management rules). When NIS2 is not enabled, these files SHALL NOT be deployed.

#### Scenario: NIS2 enabled project init
- **WHEN** `set-project init` runs on a project with `compliance.nis2.enabled: true`
- **THEN** `.claude/rules/security-nis2.md`, `.claude/rules/logging-audit.md`, `.claude/rules/supply-chain.md` are present in the project

#### Scenario: NIS2 disabled project init
- **WHEN** `set-project init` runs on a project without NIS2 enabled
- **THEN** the three NIS2 rule files are NOT deployed (existing security.md and auth-conventions.md still deployed as before)

### Requirement: Audit trail verification rule
The system SHALL include a verification rule `audit-trail-coverage` that checks API route files reference an audit logging utility. The rule SHALL use the `file-mentions` check type targeting `src/app/api/**/*.ts` files, looking for patterns like `audit.log`, `audit.track`, or `audit.record`. Severity: error.

#### Scenario: API route with audit logging
- **WHEN** a file `src/app/api/users/route.ts` contains `await audit.log({ action: "user.create", ... })`
- **THEN** the `audit-trail-coverage` rule passes for that file

#### Scenario: API route without audit logging
- **WHEN** a file `src/app/api/orders/route.ts` has no reference to audit logging
- **THEN** the `audit-trail-coverage` rule reports an error for that file

### Requirement: Security headers verification rule
The system SHALL include a verification rule `security-headers-present` that checks `next.config.*` contains security header configuration. The rule SHALL look for mentions of Content-Security-Policy, X-Frame-Options, or Strict-Transport-Security. Severity: error.

#### Scenario: Security headers configured
- **WHEN** `next.config.js` contains a `headers()` function with CSP and HSTS entries
- **THEN** the `security-headers-present` rule passes

#### Scenario: Security headers missing
- **WHEN** `next.config.js` has no security header configuration
- **THEN** the `security-headers-present` rule reports an error

### Requirement: Unsafe crypto verification rule
The system SHALL include a verification rule `no-unsafe-crypto` using `pattern-absence` check that forbids weak cryptographic patterns in source files: MD5 hashing (`createHash('md5')`), SHA1 hashing (`createHash('sha1')`), and `Math.random()` used for security-sensitive values (tokens, secrets, keys, passwords, salts, nonces). Severity: error.

#### Scenario: Code uses MD5
- **WHEN** a source file contains `crypto.createHash('md5')`
- **THEN** the `no-unsafe-crypto` rule reports an error

#### Scenario: Code uses crypto.randomUUID
- **WHEN** a source file uses `crypto.randomUUID()` for token generation
- **THEN** the `no-unsafe-crypto` rule passes (only `Math.random` flagged)

### Requirement: Rate limiting verification rule
The system SHALL include a verification rule `rate-limit-on-auth` that checks auth-related API routes reference rate limiting. The rule SHALL target `src/app/api/auth/**/*.ts` looking for patterns like `rateLimit`, `rateLimiter`, or `throttle`. Severity: warning.

#### Scenario: Auth endpoint with rate limiting
- **WHEN** `src/app/api/auth/login/route.ts` imports and uses a rate limiter
- **THEN** the `rate-limit-on-auth` rule passes

#### Scenario: Auth endpoint without rate limiting
- **WHEN** `src/app/api/auth/register/route.ts` has no rate limiting reference
- **THEN** the `rate-limit-on-auth` rule reports a warning

### Requirement: NIS2 forbidden patterns
The system SHALL add forbidden patterns to the lint gate when NIS2 compliance is enabled:
1. `eval()` calls — critical severity (code injection, Art.21(2)(e))
2. `document.write()` — critical severity (XSS vector)
3. `innerHTML =` direct assignment — warning severity (prefer textContent or sanitized HTML)
4. `console.log/debug/info` in API routes — warning severity (use structured logger)
5. Hardcoded credentials (password/secret/token/api_key literals) — critical severity (Art.21(2)(h))

#### Scenario: eval detected in source
- **WHEN** a `.ts` file contains `eval(userInput)`
- **THEN** the lint gate reports a critical finding with message referencing NIS2 Art.21(2)(e)

#### Scenario: Hardcoded credential detected
- **WHEN** a source file contains `const apiKey = "sk-abc123def456"`
- **THEN** the lint gate reports a critical finding referencing NIS2 Art.21(2)(h)

### Requirement: Compliance config flag
The system SHALL read `compliance.nis2.enabled` from `set/orchestration/config.yaml`. When the flag is `true`, NIS2 verification rules, forbidden patterns, and the security-audit gate are active. When `false` or absent, these additions are completely inactive. This ensures zero overhead for non-NIS2 projects.

#### Scenario: Config flag true
- **WHEN** `config.yaml` contains `compliance: { nis2: { enabled: true } }`
- **THEN** NIS2 verification rules appear in `get_verification_rules()` output and NIS2 forbidden patterns in `get_forbidden_patterns()` output

#### Scenario: Config flag absent
- **WHEN** `config.yaml` has no `compliance` section
- **THEN** `get_verification_rules()` returns only standard web rules, `get_forbidden_patterns()` returns only standard patterns
