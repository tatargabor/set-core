# Spec: NIS2 E2E Scaffold

## ADDED Requirements

## IN SCOPE
- New scaffold `micro-web-nis2` at `tests/e2e/scaffolds/micro-web-nis2/`
- Extends micro-web with: login page, audit log viewer page, security headers in next.config
- Scaffold spec with NIS2-relevant requirements (auth, audit logging, secure headers)
- Conventions rule file documenting the NIS2-specific project structure
- Runner script `run-micro-web-nis2.sh` that initializes with `compliance.nis2.enabled: true`
- Gate validation step confirming NIS2 rules and security-audit gate activate

## OUT OF SCOPE
- Real authentication backend (NextAuth, clerk, etc.) — uses mock/simulated auth
- Real database — login uses hardcoded credentials, audit log uses in-memory array
- Production-grade audit logging infrastructure
- Full application E2E orchestration run (scaffold is for gate enforcement testing)

### Requirement: Scaffold directory structure
The scaffold SHALL be at `tests/e2e/scaffolds/micro-web-nis2/` with:
- `scaffold.yaml` — `project_type: web`, `template: nextjs`
- `docs/spec.md` — project spec with NIS2-relevant features
- `set/orchestration/config.yaml` — config with `compliance.nis2.enabled: true`
- `templates/rules/micro-web-nis2-conventions.md` — project conventions

#### Scenario: Scaffold files complete
- **WHEN** the scaffold directory is listed
- **THEN** all four paths exist with correct content

### Requirement: Scaffold spec content
The spec SHALL define a 7-page Next.js app extending micro-web's 5 pages with:
1. **Login Page (`/login`)** — email/password form, client-side validation, simulated auth (hardcoded valid credentials), sets a cookie/localStorage token, redirects to home
2. **Audit Log Page (`/audit`)** — protected (requires login), displays a table of audit events (timestamp, user, action, resource, outcome), data from hardcoded array in `src/lib/audit-data.ts`

Plus micro-web's original 5 pages (Home, About, Contact, Blog, Blog Detail), where:
- Home and Audit pages require authentication (redirect to /login if not logged in)
- About, Contact, Blog pages are public

The spec SHALL include NIS2-specific requirements:
- REQ-SEC-01: Security headers configured in next.config.js (CSP, HSTS, X-Frame-Options, X-Content-Type-Options)
- REQ-SEC-02: Auth middleware protects /audit route
- REQ-SEC-03: Audit log entries have structured format (timestamp, userId, action, resource, outcome)
- REQ-SEC-04: Login form has rate limiting logic (client-side counter, lock after 5 failed attempts)
- REQ-SEC-05: No hardcoded secrets in source (use env vars)

#### Scenario: Spec is NIS2-testable
- **WHEN** the orchestrator decomposes the spec
- **THEN** at least one change touches security headers (testable by security-audit gate) and at least one change creates auth + audit logging (testable by verification rules)

### Requirement: Orchestration config with NIS2
The scaffold's `set/orchestration/config.yaml` SHALL include:
```yaml
compliance:
  nis2:
    enabled: true
```
Plus standard settings (max_parallel, e2e_timeout, merge_policy, etc.).

#### Scenario: Config activates NIS2
- **WHEN** the profile loads this config
- **THEN** `compliance.nis2.enabled` reads as `true`, NIS2 rules and gate are active

### Requirement: Runner script
A runner script `tests/e2e/runners/run-micro-web-nis2.sh` SHALL initialize the scaffold following the same pattern as `run-micro-web.sh`: preflight checks, git init, spec copy, `set-project init`, scaffold template deployment, gate validation. The gate validation step SHALL additionally verify that the security-audit gate is registered and NIS2 verification rules are loaded.

#### Scenario: Runner creates valid project
- **WHEN** `run-micro-web-nis2.sh` completes successfully
- **THEN** the project directory has v0-spec and v1-ready tags, web profile loads, security-audit gate is registered, and NIS2 verification rules count is higher than standard web rules count

### Requirement: Conventions rule file
The conventions file SHALL document:
- Project has auth (login page with simulated credentials)
- Audit log page is protected, requires authentication
- Security headers are mandatory in next.config.js
- No database — all data hardcoded in `src/lib/` files
- Auth state via cookie/localStorage (no server sessions)
- Audit data in `src/lib/audit-data.ts` (hardcoded array)
- Rate limiting is client-side only (counter + lockout)

#### Scenario: Conventions guide agent behavior
- **WHEN** an agent reads the conventions file during implementation
- **THEN** it knows to use hardcoded data, client-side auth, and mandatory security headers
