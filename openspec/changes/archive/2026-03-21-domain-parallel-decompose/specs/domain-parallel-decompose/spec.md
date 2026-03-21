# Delta Spec: domain-parallel-decompose

## ADDED Requirements

## IN SCOPE
- 3-phase planning pipeline (brief → domain decompose → merge)
- Parallel execution of Phase 2 domain agents via threading
- Planning brief JSON format with domain priorities, resource ownership, cross-cutting changes
- Per-domain decompose with scoped context (domain reqs + brief + conventions)
- Merge phase: dependency resolution, conflict detection, phase assignment, coverage validation
- Selective replan based on trigger type (domain fail, E2E fail, spec change, coverage gap)
- All phases use opus model

## OUT OF SCOPE
- Inter-agent messaging during Phase 2 (agents are independent, coordinated via brief)
- Changes to orchestration-plan.json output format
- Changes to digest pipeline
- Sub-domain splitting for very large domains
- Real-time progress reporting during decompose phases

### Requirement: Planning brief generation
The planning pipeline SHALL produce a JSON planning brief as Phase 1, providing shared context for all domain agents.

#### Scenario: Brief generation from digest
- **WHEN** `run_planning_pipeline()` is called in digest mode
- **THEN** Phase 1 SHALL make a single Claude API call with all domain summaries, dependencies, conventions, and test infrastructure as input
- **AND** the output SHALL be a JSON object with fields: `domain_priorities` (ordered list), `resource_ownership` (map of file patterns to owning domain), `cross_cutting_changes` (list of changes that span domains), `phasing_strategy` (text description)
- **AND** the model SHALL be opus

#### Scenario: Brief generation with single domain
- **WHEN** the digest contains only one domain
- **THEN** Phase 1 SHALL still produce a planning brief
- **AND** `cross_cutting_changes` SHALL be empty
- **AND** `resource_ownership` SHALL assign all resources to that domain

### Requirement: Per-domain parallel decompose
Phase 2 SHALL decompose each domain independently in parallel, producing per-domain change lists.

#### Scenario: Domain decompose execution
- **WHEN** Phase 2 executes
- **THEN** one Claude API call SHALL be made per domain, in parallel via threading
- **AND** each call SHALL receive: the domain's requirements, the domain summary, the planning brief from Phase 1, project conventions, and test infrastructure context
- **AND** each call SHALL NOT receive other domains' requirements
- **AND** the model SHALL be opus

#### Scenario: Domain agent output format
- **WHEN** a domain agent completes
- **THEN** the output SHALL be a JSON object with a `changes` array
- **AND** each change SHALL have: `name`, `scope`, `complexity`, `change_type`, `requirements` (list of req IDs from this domain), `model`, `has_manual_tasks`, `gate_hints`
- **AND** changes SHALL NOT reference resources owned by other domains (per the planning brief)

#### Scenario: Domain agent respects resource ownership
- **WHEN** a domain agent plans changes
- **AND** the planning brief assigns a resource to another domain
- **THEN** the domain agent SHALL NOT create changes that modify that resource
- **AND** if the domain needs that resource modified, it SHALL note this in an `external_dependencies` field on the change

### Requirement: Merge and resolve phase
Phase 3 SHALL merge all domain plans into a unified plan with resolved dependencies and validated coverage.

#### Scenario: Merge execution
- **WHEN** Phase 3 executes
- **THEN** a single Claude API call SHALL be made with all domain plans, the planning brief, and the dependency graph as input
- **AND** the model SHALL be opus

#### Scenario: Cross-domain dependency resolution
- **WHEN** domain plans contain `external_dependencies`
- **THEN** Phase 3 SHALL create `depends_on` relationships between the dependent change and the change that owns the resource
- **AND** if no owning change exists, Phase 3 SHALL create a cross-cutting change for it

#### Scenario: Conflict detection
- **WHEN** two domain agents planned changes that modify the same file or resource
- **THEN** Phase 3 SHALL detect the conflict
- **AND** either merge the changes or create a `depends_on` to serialize them

#### Scenario: Phase assignment
- **WHEN** merging domain plans
- **THEN** Phase 3 SHALL assign `phase` numbers using topological sort of the dependency graph
- **AND** changes with no dependencies SHALL be in the earliest possible phase
- **AND** `depends_on` edges SHALL be respected (dependent change in later phase)

#### Scenario: Coverage validation
- **WHEN** the merged plan is complete
- **THEN** Phase 3 SHALL verify every requirement from the digest is covered by at least one change
- **AND** uncovered requirements SHALL be assigned to new changes or flagged in `deferred_requirements`

#### Scenario: Output format
- **WHEN** Phase 3 completes
- **THEN** the output SHALL be a valid `orchestration-plan.json` with the same schema as the current single-call decompose
- **AND** downstream consumers (engine, dispatcher, verifier) SHALL see no difference

### Requirement: Selective replan
The replan system SHALL re-run only the phases needed based on the trigger type.

#### Scenario: Domain-level failure triggers domain replan
- **WHEN** a change fails or stalls
- **THEN** replan SHALL re-run Phase 2 for the owning domain only
- **AND** re-run Phase 3 to re-merge
- **AND** other domain plans SHALL be preserved

#### Scenario: E2E failure triggers merge-only replan
- **WHEN** an E2E or integration test fails
- **THEN** replan SHALL re-run Phase 3 only
- **AND** dependency ordering or phasing SHALL be adjusted based on the failure context

#### Scenario: Spec change triggers full replan
- **WHEN** the input spec changes (hash mismatch)
- **THEN** replan SHALL re-run all 3 phases (full re-decompose)

#### Scenario: Coverage gap triggers targeted replan
- **WHEN** coverage validation finds uncovered requirements
- **THEN** replan SHALL re-run Phase 2 for the domains containing uncovered requirements
- **AND** re-run Phase 3 to merge the new changes
