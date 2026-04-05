# Design: NIS2 Compliance Layer

## Context

set-core's web module already has a rich extension point system: verification rules, forbidden patterns, gate registration, orchestration directives, and template rules. NIS2 compliance requirements map naturally onto these existing abstractions. The challenge is making it opt-in without adding complexity for non-NIS2 projects.

Current state:
- `WebProjectType` has 11 verification rules, 4 forbidden patterns, 2 gates (e2e + lint)
- Config is read from `set/orchestration/config.yaml` via `_read_orch_config()` in the engine
- Gate pipeline is constructed dynamically from profile's `register_gates()`
- Template rules are deployed from `modules/web/set_project_web/templates/nextjs/rules/`

## Goals / Non-Goals

**Goals:**
- Opt-in NIS2 compliance layer activated by a single config flag
- Zero impact on existing non-NIS2 projects (no new rules, gates, or patterns)
- NIS2 rules use existing check types (pattern-absence, file-mentions) — no new verification engine changes
- Security-audit gate follows the same `GateDefinition` pattern as e2e and lint gates
- E2E scaffold validates the compliance layer end-to-end

**Non-Goals:**
- Runtime security enforcement (WAF, SIEM)
- External tool integration (CodeQL, Snyk, Trivy)
- Compliance report generation
- CoreProfile-level NIS2 rules (web-only for now; can be promoted later)

## Decisions

### 1. Config reading: Profile reads orch config

**Decision**: `WebProjectType` reads `compliance.nis2.enabled` from the orchestration config via the existing `_read_orch_config()` helper used by the engine. The profile needs access to the project root to find the config file.

**Alternative considered**: New `ComplianceConfig` dataclass in `profile_types.py`. Rejected — too much ceremony for a boolean flag. The config dict approach is already established for `merge_policy`, `max_parallel`, etc.

**Implementation**: Add a `_is_nis2_enabled(self, project_path: str) -> bool` helper to `WebProjectType` that reads the config and returns the flag value. All NIS2-conditional methods call this.

```python
def _is_nis2_enabled(self, project_path: str) -> bool:
    config_path = Path(project_path) / "set" / "orchestration" / "config.yaml"
    if not config_path.is_file():
        return False
    import yaml
    data = yaml.safe_load(config_path.read_text()) or {}
    return bool(data.get("compliance", {}).get("nis2", {}).get("enabled", False))
```

**Problem**: `get_verification_rules()` and `get_forbidden_patterns()` don't receive `project_path`. The gate executor does (via `ctx.worktree`), but the profile methods are called without project context.

**Solution**: The profile is loaded with `load_profile(project_path)` — store the path at load time. `CoreProfile.__init__` already receives `project_root` from the loader. Use `self._project_root` which is set during profile loading.

### 2. Conditional rule injection

**Decision**: `get_verification_rules()` and `get_forbidden_patterns()` check `self._is_nis2_enabled(self._project_root)` and append NIS2 rules only when true.

```python
def get_verification_rules(self) -> List[VerificationRule]:
    base_rules = super().get_verification_rules()
    web_rules = [...]  # existing 11 rules
    rules = base_rules + web_rules

    if self._is_nis2_enabled(self._project_root):
        rules.extend(self._nis2_verification_rules())
    return rules
```

**Alternative**: Separate `Nis2ComplianceMixin` class. Rejected — overengineered for 4 extra rules and 5 patterns.

### 3. Gate registration: Conditional in register_gates()

**Decision**: The `security-audit` gate is only registered when NIS2 is enabled. `register_gates()` checks the config flag.

```python
def register_gates(self) -> list:
    gates = super().register_gates() + [e2e_gate, lint_gate]
    if self._is_nis2_enabled(self._project_root):
        gates.append(GateDefinition(
            "security-audit",
            execute_security_audit_gate,
            position="after:test",
            defaults={"foundational": "run", "feature": "run",
                      "cleanup-before": "soft", "cleanup-after": "soft"},
            result_fields=("security_result", "gate_security_ms"),
            retry_counter="security_retry_count",
        ))
    return gates
```

### 4. Gate executor: Three sub-checks

**Decision**: The gate executor runs three checks sequentially:
1. **Dependency audit** — `{pm} audit --json`, parse for high/critical
2. **Security headers** — grep `next.config.*` for required headers
3. **Crypto patterns** — scan `.ts`/`.tsx` for weak crypto

Any critical sub-check failure → gate fails. Warnings are collected but don't block.

```
execute_security_audit_gate(change, project_root, worktree, ...)
  ├── dep_audit_result = run_dep_audit(worktree)     # npm/pnpm audit
  ├── header_result = check_security_headers(worktree) # grep next.config
  ├── crypto_result = scan_weak_crypto(worktree)       # regex scan
  └── aggregate → GateResult(passed, warnings, retry_context)
```

**Alternative**: Run checks in parallel with asyncio. Rejected — they're all fast (<5s each), sequential is simpler and easier to debug.

### 5. Template rules: Always deployed, effect controlled by agent context

**Decision**: The three NIS2 rule files (`security-nis2.md`, `logging-audit.md`, `supply-chain.md`) are deployed to ALL web projects by `set-project init`, but they include a frontmatter gate:

```yaml
---
description: NIS2 security compliance patterns
globs: ["src/**"]
alwaysApply: false
---
# NIS2 Security Patterns (Article 21)
> **Activation**: These rules apply when `compliance.nis2.enabled: true` is set
> in `set/orchestration/config.yaml`. If NIS2 compliance is not enabled, ignore this file.
```

**Why always deploy**: The alternative (conditional deploy in `set-project init`) requires the init logic to read orchestration config, which is a Layer 1 concern. Simpler to always deploy and let the agent self-gate via the instruction in the file. The verification rules and gate are the hard enforcement — template rules are soft guidance.

### 6. E2E scaffold: micro-web + 2 NIS2 features

**Decision**: The `micro-web-nis2` scaffold is a copy of micro-web's structure with two additions:
1. **Login page** (`/login`) — tests auth patterns, rate limiting
2. **Audit log page** (`/audit`) — tests audit trail, protected routes

This is minimal but sufficient to trigger all NIS2 gate checks:
- Security headers in `next.config.js` → header validation sub-check
- Auth endpoints → `rate-limit-on-auth` rule
- API routes → `audit-trail-coverage` rule
- Dependencies → dep audit sub-check

The scaffold does NOT include a database — all data is hardcoded arrays, same as micro-web. Auth is simulated (hardcoded credentials, localStorage token).

### 7. Runner script: Extends micro-web runner pattern

**Decision**: `run-micro-web-nis2.sh` follows the exact same structure as `run-micro-web.sh` (preflight, init, gate validation) but:
- Uses `micro-web-nis2` scaffold
- Config includes `compliance.nis2.enabled: true`
- Gate validation additionally checks security-audit gate is registered and NIS2 rule count

## Risks / Trade-offs

- **[Risk] Config path dependency** — `_is_nis2_enabled` reads yaml on every call. → Mitigation: Cache on first read (profile lifetime = one orchestration run).
- **[Risk] npm audit flaky** — network dependency, registry outages. → Mitigation: Gate returns `warn` (not fail) on network error, with retry context.
- **[Risk] Template rules deployed but inactive** — may confuse developers. → Mitigation: Clear activation instruction in the file header.
- **[Risk] False positives in crypto scan** — `Math.random()` used legitimately (UI animations, non-security). → Mitigation: Pattern requires security context words (token, secret, key, etc.) near `Math.random()`.

## Open Questions

1. Should `_is_nis2_enabled` also check `compliance.nis2.level` (essential vs important) to adjust severity? Deferred — start with single boolean, add level-based tuning later if needed.
2. Should the dep audit cache results to avoid re-running on retry? Probably yes, but not in v1.
