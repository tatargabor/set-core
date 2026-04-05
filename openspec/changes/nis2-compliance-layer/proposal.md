# Proposal: NIS2 Compliance Layer

## Why

EU NIS2 directive (2022/2555) mandates 10 cybersecurity risk-management measures for organizations in 18 critical sectors. Many of these translate directly to automated checks in CI/CD pipelines and quality gates. set-core's web template already has basic security rules (OWASP patterns, secret exposure), but lacks structured NIS2 coverage: audit logging patterns, supply chain security, cryptographic policy enforcement, and a dedicated security audit gate. Adding an opt-in NIS2 compliance layer makes set-core valuable for teams building regulated web applications.

## What Changes

- **New template rules**: `security-nis2.md` (NIS2-specific coding patterns), `logging-audit.md` (structured audit trail), `supply-chain.md` (dependency management)
- **New verification rules** in `WebProjectType`: `audit-trail-coverage`, `security-headers-present`, `no-unsafe-crypto`, `rate-limit-on-auth`
- **New forbidden patterns**: `eval()`, `document.write`, hardcoded credentials, unstructured `console.log` in API routes
- **New `security-audit` gate**: dedicated gate running dependency audit + security header check + crypto pattern scan
- **Opt-in compliance config**: `compliance.nis2.enabled` in `set/orchestration/config.yaml` controls whether NIS2 rules/gates activate
- **New E2E scaffold** `micro-web-nis2`: extends micro-web with auth login page, audit log viewer, and security headers — validates NIS2 gate enforcement
- **New E2E runner** `run-micro-web-nis2.sh`: initializes the NIS2 scaffold with compliance config enabled

## Capabilities

### New Capabilities
- `nis2-compliance-rules` — Template rules and verification rules for NIS2 Article 21 compliance
- `security-audit-gate` — Dedicated quality gate for automated security auditing (dep audit, headers, crypto)
- `nis2-e2e-scaffold` — E2E test scaffold for validating NIS2 compliance enforcement

### Modified Capabilities
_(none — this is additive, no existing spec behavior changes)_

## Impact

- **`modules/web/set_project_web/project_type.py`**: New verification rules, forbidden patterns, gate registration (conditional on compliance config)
- **`modules/web/set_project_web/gates.py`**: New `execute_security_audit_gate()` executor
- **`modules/web/set_project_web/templates/nextjs/`**: 3 new rule files
- **`lib/set_orch/profile_types.py`**: May need `ComplianceConfig` dataclass (or reuse existing config dict)
- **`tests/e2e/scaffolds/micro-web-nis2/`**: New scaffold directory
- **`tests/e2e/runners/run-micro-web-nis2.sh`**: New runner script
- No breaking changes — all NIS2 features are opt-in via config
