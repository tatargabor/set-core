## ADDED Requirements

<!--
IN SCOPE:
- On replan, look up `domains-plans-<lineage>.json` and reuse cached domain plans whose input hasn't changed.
- Domain-input hashing (digest summary + requirements + planning brief).
- Reuse logic for the 3-phase parallel path.
- Reuse logic for the serial path (whole-plan reuse on identical digest input).
- Telemetry recording how many domains were reused vs re-planned.

OUT OF SCOPE:
- Generating the saved domain plans (that's `orch-plan-python`).
- Diff-update digest pipeline (that's `digest-diff-update`).
- The replan trigger logic itself (that's `orch-replan-python`).
-->

### Requirement: Replan looks up saved domain plans
On replan in the parallel path, before invoking Phase 1 or Phase 2, the system SHALL look up `domains-plans-<lineage>.json` via `LineagePaths.plan_domains_file`. If the file exists and is parseable, the system SHALL load the saved planning brief and per-domain plans into memory.

#### Scenario: Saved file present and valid
- **WHEN** a replan fires AND `domains-plans-<lineage>.json` exists with valid JSON containing `brief` and `domain_plans` keys
- **THEN** the system SHALL load both into the replan context
- **AND** SHALL log at INFO level: `replan: loaded saved domain plans (<N> domains)`

#### Scenario: Saved file missing
- **WHEN** a replan fires AND `domains-plans-<lineage>.json` does not exist
- **THEN** the system SHALL proceed with a full Phase 1 + Phase 2 run as today
- **AND** SHALL NOT raise an error

#### Scenario: Saved file unparseable
- **WHEN** a replan fires AND the saved file exists but is malformed JSON
- **THEN** the system SHALL log at WARNING level and proceed with a full run

### Requirement: Domain input hashing
For each domain, the system SHALL compute a stable input hash from the concatenation of: that domain's summary text, its requirements JSON, the planning brief JSON, and the conventions text. The hash SHALL be `sha256` over the UTF-8 encoded concatenation in a fixed order.

#### Scenario: Hash function determinism
- **WHEN** the same inputs are hashed twice
- **THEN** the resulting `sha256` hex digests SHALL be byte-identical

#### Scenario: Hash inputs are ordered
- **WHEN** the hash is computed for domain `auth`
- **THEN** the hashed bytes SHALL be `domain_summary || \n || requirements_json || \n || brief_json || \n || conventions` (UTF-8)
- **AND** the order of components SHALL NOT depend on dict iteration order

### Requirement: Per-domain reuse decision
For each domain in the new digest, the system SHALL compute its current input hash and compare to the saved hash from `domains-plans-<lineage>.json`. If the hashes match, the system SHALL reuse the saved domain plan and SHALL NOT invoke Phase 2 for that domain. If the hashes differ or no saved hash exists, the system SHALL invoke Phase 2 for that domain.

#### Scenario: Unchanged domain reused
- **WHEN** domain `cart` has hash `abc123` in the saved file AND the current computed hash for `cart` is also `abc123`
- **THEN** the system SHALL reuse `saved_domain_plans["cart"]` directly
- **AND** SHALL NOT invoke `_decompose_single_domain` for `cart`
- **AND** SHALL log at INFO level: `replan: domain cart reused (hash match)`

#### Scenario: Changed domain re-decomposed
- **WHEN** domain `auth` has hash `abc123` in the saved file AND the current computed hash for `auth` is `def456`
- **THEN** the system SHALL invoke `_decompose_single_domain` for `auth`
- **AND** SHALL include `auth` in the Phase 2 fan-out
- **AND** SHALL log at INFO level: `replan: domain auth re-decomposed (hash changed)`

#### Scenario: Brief change invalidates all domains
- **WHEN** the new planning brief differs from the saved brief
- **THEN** every domain hash SHALL recompute to a different value (because the brief is part of the hash input)
- **AND** every domain SHALL be re-decomposed

### Requirement: Domain-input hashes persisted alongside plans
When `_save_domain_plans` writes `domains-plans-<lineage>.json`, the file SHALL include each domain's input hash in a top-level `domain_input_hashes` field, keyed by domain name.

#### Scenario: Saved file shape includes hashes
- **WHEN** `_save_domain_plans` runs after a successful Phase 2
- **THEN** the resulting JSON SHALL have shape `{"brief": {...}, "domain_plans": {...}, "domain_input_hashes": {"<name>": "<sha256>"}, "created_at": "..."}`

### Requirement: Reuse telemetry in LLM_CALL events
When a replan reuses one or more saved domain plans, the system SHALL emit a `REPLAN_REUSE` event recording the count of reused domains and the count of re-decomposed domains.

#### Scenario: Reuse event content
- **WHEN** a replan reuses 11 of 13 domains
- **THEN** a `REPLAN_REUSE` event SHALL be emitted with payload `{"reused": 11, "redecomposed": 2, "total": 13}`

### Requirement: Reuse applies to serial path via whole-plan check
On replan in the serial path, when the digest input hash matches the previous decompose's input hash AND `replan_ctx` is empty (no completion delta to apply), the system SHALL reuse the previous plan unchanged and SHALL NOT invoke Claude.

#### Scenario: Identical replan in serial mode
- **WHEN** the digest content has not changed AND `replan_ctx.completed` is empty
- **THEN** the serial path SHALL skip the Claude call
- **AND** SHALL log at INFO level: `replan: plan unchanged (hash match) — reusing prior plan`
- **AND** SHALL NOT emit a decompose `LLM_CALL` event

#### Scenario: Replan context forces re-run in serial mode
- **WHEN** the digest content is unchanged BUT `replan_ctx.completed` is non-empty
- **THEN** the serial path SHALL invoke Claude (the completion context is volatile and may shift the plan)
