## MODIFIED Requirements

### Requirement: Ambiguity detection
The digest SHALL identify underspecified, contradictory, or missing-reference issues in the spec and report them in `ambiguities.json`. Each ambiguity entry SHALL include `id`, `type`, `source`, `section`, `description`, and `affects_requirements`. After triage processing, entries SHALL also contain `resolution`, `resolution_note`, and `resolved_by` fields.

#### Scenario: Underspecified behavior detected
- **WHEN** a spec file describes a behavior without sufficient detail (e.g., "cart merge on login" without specifying duplicate handling strategy)
- **THEN** `ambiguities.json` contains an entry with `type: "underspecified"` and a description of what is missing

#### Scenario: Missing cross-reference detected
- **WHEN** feature A references a template/entity/behavior in feature B that does not exist in B's spec file (e.g., subscription.md references "payment failure email" but email-notifications.md has no such template)
- **THEN** `ambiguities.json` contains an entry with `type: "missing_reference"` listing both source and target files

#### Scenario: Contradictory definitions detected
- **WHEN** two spec files define the same concept differently (e.g., shipping rates defined in both cart-checkout.md and subscription.md with different values)
- **THEN** `ambiguities.json` contains an entry with `type: "contradictory"` listing both sources

#### Scenario: Ambiguities shown in dry-run
- **WHEN** user runs `set-orchestrate digest --dry-run`
- **THEN** detected ambiguities are printed to stdout in a human-readable format

#### Scenario: Resolution fields present after triage
- **WHEN** ambiguity AMB-003 has been triaged as `defer` with note "planner decides"
- **THEN** `ambiguities.json` entry for AMB-003 contains `"resolution": "deferred"`, `"resolution_note": "planner decides"`, `"resolved_by": "triage"`

#### Scenario: Untriaged ambiguities have no resolution fields
- **WHEN** digest generates fresh `ambiguities.json` before any triage
- **THEN** entries do NOT contain `resolution`, `resolution_note`, or `resolved_by` fields

### Requirement: Digest generation
The system SHALL process a multi-file spec into a structured digest at `wt/orchestration/digest/`. The digest contains: `index.json` (file manifest with `spec_base_dir`), `conventions.json` (project-wide rules), `data-definitions.md` (entity/catalog summaries), `requirements.json` (behavioral requirements with IDs), `dependencies.json` (requirement cross-references), `coverage.json` (initially empty `{}`), `ambiguities.json` (detected spec issues), `triage.md` (human triage template, generated only when ambiguities exist), and `domains/*.md` (domain summaries).

#### Scenario: Digest from directory spec
- **WHEN** user runs `set-orchestrate digest --spec docs/v1-project/`
- **THEN** the system creates `wt/orchestration/digest/` with all output types including `triage.md` if ambiguities were detected

#### Scenario: Triage template generated as part of digest output
- **WHEN** digest generates `ambiguities.json` with entries
- **THEN** `triage.md` is generated in the same atomic write operation
