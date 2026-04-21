## ADDED Requirements

### Requirement: E2E manifest history append on merge
When a change merges successfully, the merger SHALL append the change's current `e2e-manifest.json` contents to `e2e-manifest-history.jsonl` in the project root as a single JSON line annotated with the change name, plan version, session id, and merge timestamp.

#### Scenario: Merge with passing E2E manifest
- **WHEN** change "foundation-setup" merges and its worktree `e2e-manifest.json` lists 15 passing tests
- **THEN** a line `{ "change": "foundation-setup", "plan_version": <V>, "sentinel_session_id": <UUID>, "merged_at": "<iso>", "manifest": <full e2e-manifest.json object> }` SHALL be appended to `e2e-manifest-history.jsonl`
- **AND** the per-worktree `e2e-manifest.json` SHALL remain in place for the current test-run view (unchanged)

#### Scenario: Merge with missing manifest
- **WHEN** a change merges but its worktree never generated an `e2e-manifest.json`
- **THEN** no line SHALL be appended
- **AND** the merger SHALL log at DEBUG that the manifest was missing (not WARNING — absence is legitimate for changes that skip tests)

### Requirement: E2E manifest history carries lineage
Every `e2e-manifest-history.jsonl` line SHALL carry `spec_lineage_id`, and the Digest/E2E endpoint SHALL accept `?lineage=<id>` to filter the aggregation to a single lineage.

#### Scenario: v1 e2e manifest while v2 is running
- **WHEN** the client calls `GET /api/<project>/digest/e2e?lineage=docs/spec-v1.md`
- **THEN** only v1-tagged manifest history lines SHALL contribute to the returned blocks
- **AND** v2's live manifests SHALL NOT appear in the v1 response

### Requirement: Digest E2E aggregates across cycles
The Digest/E2E API SHALL combine the live per-change manifests with every entry in `e2e-manifest-history.jsonl`, so archived test blocks are visible alongside current ones.

#### Scenario: Archived + live blocks
- **WHEN** live plan has change "promotions-engine" with a current manifest of 28 tests
- **AND** `e2e-manifest-history.jsonl` has three archived entries (foundation-setup: 15 tests, auth-and-accounts: 12 tests, product-catalog: 20 tests)
- **THEN** the Digest/E2E response SHALL include all four blocks, each labelled with its originating change name
- **AND** the header SHALL read "75 tests across 4 change(s)" (or equivalent aggregated wording)
- **AND** archived blocks SHALL carry an `archived = true` flag so the UI can style them distinctly

#### Scenario: Legacy archive without history
- **WHEN** `e2e-manifest-history.jsonl` does not exist (legacy run)
- **THEN** the API SHALL fall back to current behaviour (live manifests only) without raising
