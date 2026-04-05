# Tasks: NIS2 Compliance Layer

## 1. Config Reading Infrastructure

- [ ] 1.1 Add `_is_nis2_enabled(self, project_path: str) -> bool` helper to `WebProjectType` that reads `compliance.nis2.enabled` from `set/orchestration/config.yaml` [REQ: compliance-config-flag]
- [ ] 1.2 Ensure `self._project_root` is available in `WebProjectType` (set during profile loading in `profile_loader.py`) [REQ: compliance-config-flag]
- [ ] 1.3 Add caching to `_is_nis2_enabled` so yaml is only parsed once per profile lifetime [REQ: compliance-config-flag]

## 2. Template Rule Files

- [ ] 2.1 Create `modules/web/set_project_web/templates/nextjs/rules/security-nis2.md` — NIS2 Article 21 coding patterns (auth checks, encryption, session management, input validation) [REQ: nis2-template-rules-deployment]
- [ ] 2.2 Create `modules/web/set_project_web/templates/nextjs/rules/logging-audit.md` — structured audit trail patterns (JSON logging, mandatory fields, append-only, CRUD audit events) [REQ: nis2-template-rules-deployment]
- [ ] 2.3 Create `modules/web/set_project_web/templates/nextjs/rules/supply-chain.md` — dependency management rules (pinned versions, lockfile, quarterly review, no --force) [REQ: nis2-template-rules-deployment]

## 3. Verification Rules

- [ ] 3.1 Add `_nis2_verification_rules()` method to `WebProjectType` returning list of NIS2-specific `VerificationRule` objects [REQ: compliance-config-flag]
- [ ] 3.2 Implement `audit-trail-coverage` rule — `file-mentions` check on `src/app/api/**/*.ts` for audit logging references [REQ: audit-trail-verification-rule]
- [ ] 3.3 Implement `security-headers-present` rule — `file-mentions` check on `next.config.*` for CSP/HSTS/X-Frame-Options [REQ: security-headers-verification-rule]
- [ ] 3.4 Implement `no-unsafe-crypto` rule — `pattern-absence` check for MD5, SHA1, Math.random+security context [REQ: unsafe-crypto-verification-rule]
- [ ] 3.5 Implement `rate-limit-on-auth` rule — `file-mentions` check on `src/app/api/auth/**/*.ts` for rate limiting [REQ: rate-limiting-verification-rule]
- [ ] 3.6 Modify `get_verification_rules()` to conditionally include NIS2 rules when `_is_nis2_enabled()` [REQ: compliance-config-flag]

## 4. Forbidden Patterns

- [ ] 4.1 Add `_nis2_forbidden_patterns()` method returning NIS2-specific forbidden pattern list [REQ: nis2-forbidden-patterns]
- [ ] 4.2 Add patterns: eval(), document.write(), innerHTML=, console.log in API routes, hardcoded credentials [REQ: nis2-forbidden-patterns]
- [ ] 4.3 Modify `get_forbidden_patterns()` to conditionally include NIS2 patterns when `_is_nis2_enabled()` [REQ: nis2-forbidden-patterns]

## 5. Security Audit Gate

- [ ] 5.1 Create `execute_security_audit_gate()` function in `modules/web/set_project_web/gates.py` [REQ: security-audit-gate-registration]
- [ ] 5.2 Implement dependency audit sub-check — run `{pm} audit --json`, parse high/critical vulnerabilities [REQ: dependency-audit-check]
- [ ] 5.3 Implement security header validation sub-check — scan next.config for required headers [REQ: security-header-validation]
- [ ] 5.4 Implement crypto pattern scan sub-check — regex scan .ts/.tsx files for weak crypto [REQ: crypto-pattern-scan]
- [ ] 5.5 Implement result aggregation and retry context formatting [REQ: gate-result-reporting]
- [ ] 5.6 Register `security-audit` gate in `WebProjectType.register_gates()` conditionally on NIS2 enabled [REQ: security-audit-gate-registration]
- [ ] 5.7 Add change-type defaults: foundational/feature/schema → run, cleanup → soft [REQ: change-type-aware-defaults]

## 6. E2E Scaffold

- [ ] 6.1 Create `tests/e2e/scaffolds/micro-web-nis2/scaffold.yaml` [REQ: scaffold-directory-structure]
- [ ] 6.2 Create `tests/e2e/scaffolds/micro-web-nis2/docs/spec.md` — 7-page app spec (micro-web 5 pages + login + audit log) with NIS2 requirements [REQ: scaffold-spec-content]
- [ ] 6.3 Create `tests/e2e/scaffolds/micro-web-nis2/set/orchestration/config.yaml` with `compliance.nis2.enabled: true` [REQ: orchestration-config-with-nis2]
- [ ] 6.4 Create `tests/e2e/scaffolds/micro-web-nis2/templates/rules/micro-web-nis2-conventions.md` [REQ: conventions-rule-file]

## 7. E2E Runner Script

- [ ] 7.1 Create `tests/e2e/runners/run-micro-web-nis2.sh` based on `run-micro-web.sh` pattern [REQ: runner-script]
- [ ] 7.2 Update runner gate validation to verify security-audit gate registration and NIS2 rule count [REQ: runner-script]
- [ ] 7.3 Test runner creates valid project with v0-spec and v1-ready tags [REQ: runner-script]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN `set-project init` runs on NIS2-enabled project THEN security-nis2.md, logging-audit.md, supply-chain.md are present [REQ: nis2-template-rules-deployment, scenario: nis2-enabled-project-init]
- [ ] AC-2: WHEN `set-project init` runs without NIS2 THEN the three NIS2 rule files are still deployed but contain self-gating instruction [REQ: nis2-template-rules-deployment, scenario: nis2-disabled-project-init]
- [ ] AC-3: WHEN config has `compliance.nis2.enabled: true` THEN NIS2 verification rules appear in `get_verification_rules()` output [REQ: compliance-config-flag, scenario: config-flag-true]
- [ ] AC-4: WHEN config has no compliance section THEN only standard web rules returned [REQ: compliance-config-flag, scenario: config-flag-absent]
- [ ] AC-5: WHEN NIS2 enabled and pipeline constructed THEN security-audit gate is between test and review [REQ: security-audit-gate-registration, scenario: gate-appears-in-pipeline]
- [ ] AC-6: WHEN `npm audit` reports critical vulnerability THEN gate fails with package name and CVE in retry context [REQ: dependency-audit-check, scenario: critical-vulnerability-found]
- [ ] AC-7: WHEN source file contains `eval(userInput)` THEN lint gate reports critical finding [REQ: nis2-forbidden-patterns, scenario: eval-detected-in-source]
- [ ] AC-8: WHEN `run-micro-web-nis2.sh` completes THEN project has web profile, security-audit gate registered, NIS2 rules loaded [REQ: runner-script, scenario: runner-creates-valid-project]
