## MODIFIED Requirements

### Requirement: Dispatch context written to input.md
When dispatching a change, the orchestrator SHALL write all dispatcher-generated context to `openspec/changes/<name>/input.md` in the worktree, separate from `proposal.md`.

For each assigned requirement (`change.requirements`), if `acceptance_criteria` is present and non-empty in `requirements.json`, the input.md SHALL include the AC items below the requirement title. If `acceptance_criteria` is absent or empty, the existing fallback to `brief` SHALL apply.

#### Scenario: input.md created on dispatch
- **WHEN** `dispatch_change("cart-actions")` runs
- **THEN** `openspec/changes/cart-actions/input.md` SHALL be created in the worktree
- **AND** it SHALL contain: Scope, Project Context, Sibling Changes, Design Context, and Assigned Requirements sections
- **AND** `proposal.md` SHALL NOT contain injected orchestration context

#### Scenario: AC items injected into input.md for assigned REQs
- **WHEN** dispatching a change with assigned requirements that have `acceptance_criteria`
- **THEN** `input.md` SHALL include an `## Assigned Requirements` section
- **AND** each REQ SHALL list its AC items as a bullet list below its title
- **AND** the format SHALL be:
  ```
  ## Assigned Requirements
  - REQ-CART-001: Add item to cart
    - POST /api/cart/items → 201 with cartItemId
    - Stock decremented by quantity
    - Returns 400 if quantity > stock
  ```

#### Scenario: Fallback to brief when AC absent
- **WHEN** dispatching a change with requirements that have no `acceptance_criteria` (old digest or empty array)
- **THEN** `input.md` SHALL show `REQ-ID: title — brief` (existing behavior)
- **AND** no error or warning is emitted

#### Scenario: Cross-cutting REQs get title only
- **WHEN** a change has `also_affects_reqs`
- **THEN** those REQs appear in `input.md` with title only, no AC items
- **AND** this matches existing behavior for cross-cutting requirements

#### Scenario: Retry context appended to input.md
- **WHEN** a change is retried with `retry_context` set in state extras
- **THEN** the retry context SHALL be appended to `input.md` under a `## Retry Context` section
- **AND** `proposal.md` SHALL NOT have retry context appended to it
