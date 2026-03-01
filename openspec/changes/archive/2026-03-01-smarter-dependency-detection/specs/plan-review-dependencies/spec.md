## ADDED Requirements

### Requirement: Dependency detection in plan review
The `/wt:plan-review` skill SHALL detect implicit ordering relationships between spec items and suggest concrete `depends_on` annotations.

#### Scenario: Cleanup change detected alongside feature changes
- **WHEN** a spec contains a cleanup/refactor change AND feature changes that touch the same area
- **THEN** the review suggests the feature changes should `depends_on` the cleanup change, with reasoning

#### Scenario: Schema migration alongside data access changes
- **WHEN** a spec contains a DB schema/migration change AND changes that query/mutate data in those tables
- **THEN** the review suggests the data access changes should `depends_on` the schema change

#### Scenario: Auth/authorization change alongside feature changes
- **WHEN** a spec contains auth, role, or permission changes AND features that require auth
- **THEN** the review suggests the features should `depends_on` the auth change

#### Scenario: Shared type definitions alongside consumers
- **WHEN** multiple spec items would extend the same type/enum/interface
- **THEN** the review suggests extracting a shared-types change OR chaining them, with the specific type file identified

#### Scenario: Output format for suggestions
- **WHEN** dependency issues are found
- **THEN** the review includes a "Suggested Dependencies" section with exact text to add to the spec, e.g.: `- Impersonation: add "depends_on: ui-cleanup-pack" (cleanup should precede feature work on shared UI)`

#### Scenario: No dependency issues found
- **WHEN** all spec items have appropriate independence or already declare dependencies
- **THEN** the review notes "Dependency ordering looks good" with a brief explanation of why items are safe to parallelize
