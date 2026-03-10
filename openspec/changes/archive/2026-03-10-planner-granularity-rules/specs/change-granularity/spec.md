## ADDED Requirements

### Requirement: Maximum requirements per change
The planner MUST NOT produce changes with more than 6 requirements. If a feature domain has more than 6 requirements, it must be split into sub-domain changes.

#### Scenario: Feature domain with 22 requirements (e.g., product-catalog)
- **WHEN** a feature domain produces 22 requirements during decomposition
- **THEN** the planner splits it into 4+ changes of 4-6 requirements each (e.g., product-list-and-filters, product-detail-and-variants, product-search, equipment-and-bundles)

#### Scenario: Feature domain with 5 requirements
- **WHEN** a feature domain produces 5 requirements
- **THEN** the planner keeps it as a single change (within the 6 REQ limit)

### Requirement: Complexity cap at M
The planner MUST NOT produce L complexity changes (15+ tasks). Maximum complexity is M (8-15 tasks). S (<8 tasks) is preferred.

#### Scenario: Decomposition would produce 25+ tasks
- **WHEN** a change scope implies more than 15 implementation tasks
- **THEN** the planner splits it into 2+ changes each with at most 15 tasks

### Requirement: Scope text length as sizing signal
The planner should use scope text length as a secondary sizing heuristic. Scope descriptions of 800-1500 characters indicate healthy sizing. Scope exceeding 2000 characters signals the change is too large.

#### Scenario: Scope description exceeds 2000 characters
- **WHEN** the planner writes a scope description that exceeds 2000 characters
- **THEN** the change should be reconsidered for splitting

### Requirement: Sub-domain dependency chaining
When a large feature domain is split into multiple changes, those changes MUST form a depends_on chain so they execute sequentially. This prevents merge conflicts on shared files within the same domain. Different domain chains can run in parallel.

#### Scenario: product-catalog split into 3 sub-changes
- **WHEN** product-catalog is split into product-list, product-detail, and product-search
- **THEN** product-detail depends_on product-list, and product-search depends_on product-detail
- **AND** these changes can run in parallel with unrelated chains (e.g., user-auth)

#### Scenario: user-auth split into 2 sub-changes
- **WHEN** user-auth-and-accounts is split into user-auth-login and user-profile-management
- **THEN** user-profile-management depends_on user-auth-login

### Requirement: Split heuristics for common patterns
The planner prompt must include concrete split heuristics for recurring patterns to guide decomposition decisions.

#### Scenario: Feature with list page + detail page + CRUD + search
- **WHEN** a feature domain includes list views, detail views, CRUD operations, and search
- **THEN** the planner applies pattern-based splitting: list+filters as one change, detail+variants as another, search as a third (if it has its own API routes)

#### Scenario: Auth feature with login + profile + password reset
- **WHEN** a feature domain includes authentication, profile management, and password reset
- **THEN** the planner splits auth/login from profile/account management

### Requirement: Both prompt locations updated
The granularity rules must appear in both the digest-mode and brief-mode decomposition prompts in planner.sh, since they share the same rule structure.

#### Scenario: Orchestration via digest pipeline
- **WHEN** the planner runs in digest mode
- **THEN** the granularity rules are present in the decomposition prompt

#### Scenario: Orchestration via brief/spec
- **WHEN** the planner runs in brief mode
- **THEN** the same granularity rules are present in the decomposition prompt
