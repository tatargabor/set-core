## MODIFIED Requirements

### Requirement: Resolver runs six deterministic detection layers per change
The change-category-resolver SHALL compute the union of categories from six per-change deterministic layers before considering LLM input. The five primary layers run unconditionally; the project-state fallback runs only when the primary union has at most two categories. When a change has non-empty `ikp_packs` in its metadata, the resolver SHALL add `"integration"` to the category set as an additional deterministic signal.

#### Scenario: All five primary layers contribute
- **WHEN** a change has change_type=`feature`, requirements=`[REQ-AUTH-001, REQ-API-USERS-001]`, manifest paths include `src/app/api/users/route.ts`, scope text contains `oauth`, depends_on includes a parent change classified as `database`
- **THEN** the resolver SHALL return a union containing at least `{general, frontend, auth, api, database}`
- **AND** the project-state fallback layer SHALL NOT run (primary union has > 2 categories)

#### Scenario: Project-state fallback engages on thin signal
- **WHEN** a change has change_type=`feature`, no requirements, no path matches, no scope intent matches, no depends_on
- **AND** the primary union yields only `{general, frontend}` (frontend from change_type defaults)
- **THEN** the resolver SHALL invoke `profile.detect_project_categories(project_path)` and union the result
- **AND** the audit log SHALL record that the fallback layer ran

#### Scenario: Layer ordering is union-based, not priority-based
- **WHEN** layer 1 returns `{frontend}` and layer 4 returns `{auth}`
- **THEN** the resolver SHALL return `{frontend, auth}` (both)
- **AND** no layer SHALL override or remove categories produced by another

#### Scenario: Change with ikp_packs
- **WHEN** a change has `ikp_packs: ["billingo"]` in its metadata
- **THEN** the resolver SHALL add `"integration"` to the deterministic category union
- **AND** SHALL include this in the audit log record

#### Scenario: Change without ikp_packs
- **WHEN** a change has no `ikp_packs` or an empty list
- **THEN** the resolver SHALL NOT add `"integration"` from this signal
- **AND** the resolver behavior SHALL be unchanged from existing logic

#### Scenario: Integration category in taxonomy
- **WHEN** the profile's `category_taxonomy()` is queried
- **THEN** it SHALL include `"integration"` as a valid category
