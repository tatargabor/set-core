## IN SCOPE
- Detection of `fix-iss-*` directories on disk that are missing from `state.changes`
- Automatic registration of detected orphans into `state.changes` with sensible defaults so the dispatcher picks them up on the next poll
- Best-effort parent attribution from `proposal.md` content
- Structured event emission so operators can audit what was adopted
- Idempotent re-runs — running the reconciler twice never produces duplicate state entries

## OUT OF SCOPE
- Auto-dispatching the fix-iss agent itself (dispatch already works once a change is in state with `status=pending`)
- Removing orphans (covered by the existing `fix-iss-orphan-cleanup` capability)
- Backfilling tasks.md or design.md content for orphans missing those files (the dispatcher tolerates partial artifacts; missing artifacts surface via existing validation paths)
- Detection of non-`fix-iss-*` orphan directories (other change types are handled by reconciliation sweep)

## ADDED Requirements

### Requirement: Reconciler scans openspec/changes for orphan fix-iss directories on each monitor poll

The orchestration monitor SHALL invoke `reconcile_fix_iss_orphans(state_file, project_root)` on each poll cycle. The function SHALL list `openspec/changes/fix-iss-*` directories, exclude any whose name already appears in `state.changes`, and produce a list of orphan directories to register.

#### Scenario: Empty directory listing produces no work

- **GIVEN** `openspec/changes/` contains no `fix-iss-*` directories
- **WHEN** the reconciler runs
- **THEN** it returns an empty result
- **AND** state.changes is unmodified
- **AND** no events are emitted

#### Scenario: Single orphan detected and registered

- **GIVEN** `openspec/changes/fix-iss-007-foo/` exists on disk with a `proposal.md`
- **AND** `state.changes` does NOT contain `fix-iss-007-foo`
- **WHEN** the reconciler runs
- **THEN** `state.changes` SHALL contain a new entry with `name="fix-iss-007-foo"`, `status="pending"`, `change_type="fix"`
- **AND** a `FIX_ISS_ORPHAN_REGISTERED` event SHALL be emitted with `data={"name": "fix-iss-007-foo", "source": "on_disk_orphan"}`

#### Scenario: Already-registered fix-iss is skipped (idempotency)

- **GIVEN** `state.changes` contains an entry named `fix-iss-007-foo` with any status
- **AND** `openspec/changes/fix-iss-007-foo/` exists on disk
- **WHEN** the reconciler runs
- **THEN** state.changes SHALL NOT gain a duplicate entry
- **AND** no `FIX_ISS_ORPHAN_REGISTERED` event SHALL be emitted for this name

#### Scenario: Multiple orphans on the same poll

- **GIVEN** two orphan directories `fix-iss-001-a` and `fix-iss-002-b` exist on disk
- **AND** neither appears in `state.changes`
- **WHEN** the reconciler runs
- **THEN** both SHALL be registered in a single locked state transaction
- **AND** two distinct `FIX_ISS_ORPHAN_REGISTERED` events SHALL be emitted (one per orphan)

### Requirement: Registration uses parent attribution heuristics

The reconciler SHALL attempt to derive `parent_name` for each orphan from its `proposal.md` content using the following ordered strategies:

1. An HTML comment of the form `<!-- parent: <name> -->` anywhere in proposal.md
2. A line matching the regex `Parent change \`([^\`]+)\`` in the Why section
3. Slug-prefix match: the orphan's slug suffix (after `fix-iss-NNN-`) compared against existing change names by prefix; the longest matching change name wins

If a confident match is found, the orphan SHALL be registered with `depends_on=[parent_name]`, `phase=parent.phase + 1` (clamped to the maximum phase already in the state's phases dict if needed). If NO match is found, the orphan SHALL be registered with `depends_on=[]` and `phase=current_phase`, so it dispatches alongside peers in the active phase rather than being permanently stalled.

#### Scenario: Explicit parent comment wins over Why-line text

- **GIVEN** `proposal.md` contains both `<!-- parent: real-parent -->` and `Parent change \`other-parent\`` text
- **WHEN** the reconciler attributes the orphan
- **THEN** the registered entry's `depends_on` SHALL be `["real-parent"]`

#### Scenario: Why-line attribution

- **GIVEN** `proposal.md` has no parent comment
- **AND** the Why section contains `Parent change \`user-account\` hit a circuit breaker`
- **WHEN** the reconciler attributes the orphan
- **THEN** the registered entry's `depends_on` SHALL be `["user-account"]`

#### Scenario: Slug-prefix fallback

- **GIVEN** an orphan named `fix-iss-002-design-fidelity-gate-blocks-us`
- **AND** the proposal.md has no parent comment or Why line
- **AND** `state.changes` contains an entry named `user-account`
- **WHEN** the reconciler attributes the orphan
- **THEN** the slug-prefix match resolves to `user-account` (best longest-prefix match)
- **AND** the registered entry's `depends_on` SHALL be `["user-account"]`

#### Scenario: No parent derivable — register with current phase

- **GIVEN** an orphan whose proposal.md and slug yield no confident parent match
- **WHEN** the reconciler attributes the orphan
- **THEN** the registered entry's `depends_on` SHALL be `[]`
- **AND** the registered entry's `phase` SHALL equal `state.current_phase`

### Requirement: Registration is safe under concurrent escalation paths

The reconciler SHALL acquire `locked_state` for its writes and SHALL skip registration when a concurrent path (e.g. `escalate_change_to_fix_iss`) has already added the same name. The duplicate-name guard already present in `_register_fix_iss_in_state` (which short-circuits on `any(c.name == fix_iss_name for c in state.changes)`) SHALL be the single source of truth for "already registered".

#### Scenario: Race with escalate_change_to_fix_iss — single registration wins

- **GIVEN** `escalate_change_to_fix_iss` and `reconcile_fix_iss_orphans` run for the same `fix-iss-007-foo` in close succession
- **WHEN** both attempt registration under `locked_state`
- **THEN** exactly one registration succeeds
- **AND** the second observes the entry already present and returns without writing

### Requirement: Reconciler emits FIX_ISS_ORPHAN_REGISTERED event distinct from FIX_ISS_ESCALATED

The reconciler SHALL emit a `FIX_ISS_ORPHAN_REGISTERED` event for each orphan it adopts. The event SHALL NOT reuse `FIX_ISS_ESCALATED` because the latter is reserved for proactive circuit-breaker-driven escalations. Operators SHALL be able to count orphans-recovered as a separate metric.

#### Scenario: Orphan registered emits orphan event

- **WHEN** an orphan is newly registered by the reconciler
- **THEN** the emitted event has `type="FIX_ISS_ORPHAN_REGISTERED"`
- **AND** `change` set to the fix-iss name
- **AND** `data` includes `source="on_disk_orphan"` and the derived `parent_name_guess` (or `null` when none)

#### Scenario: Escalation-path registration does NOT emit the orphan event

- **WHEN** `escalate_change_to_fix_iss` registers a fix-iss
- **THEN** only `FIX_ISS_ESCALATED` is emitted
- **AND** no `FIX_ISS_ORPHAN_REGISTERED` is emitted for the same name

### Requirement: Reconciler tolerates malformed orphan directories

If an orphan directory is missing `proposal.md`, the reconciler SHALL log at WARN with the directory name and the reason, then continue processing remaining orphans. A missing `tasks.md` or `design.md` SHALL NOT block registration — those files are produced during dispatch and the dispatcher tolerates their absence at registration time.

#### Scenario: Missing proposal.md skipped with warning

- **GIVEN** `openspec/changes/fix-iss-008-broken/` exists with no `proposal.md`
- **WHEN** the reconciler runs
- **THEN** the orphan is NOT registered
- **AND** a WARN log entry SHALL identify the directory and the missing file

#### Scenario: Missing tasks.md does not block registration

- **GIVEN** `openspec/changes/fix-iss-009-partial/` exists with `proposal.md` but no `tasks.md`
- **WHEN** the reconciler runs
- **THEN** the orphan IS registered as `pending`
- **AND** the dispatcher's existing tasks-creation flow handles the missing file at dispatch time
