## MODIFIED Requirements

### Requirement: Requirement review section builder
`build_req_review_section()` SHALL build an "Assigned Requirements" section for the review prompt. When a requirement has non-empty `acceptance_criteria`, the section SHALL render AC items as Markdown checkboxes instead of the plain `title — brief` line.

If `acceptance_criteria` is absent or empty (old digest or vague spec), the function SHALL fall back to the existing `title — brief` format.

#### Scenario: AC items rendered as checkboxes in review prompt
- **WHEN** `build_req_review_section()` runs for a change with requirements that have `acceptance_criteria`
- **THEN** the section SHALL render each REQ as:
  ```
  - REQ-CART-001: Add item to cart
    - [ ] POST /api/cart/items → 201 with cartItemId
    - [ ] Stock decremented by quantity
    - [ ] Returns 400 if quantity > stock
  ```
- **AND** the "Requirement Coverage Check" instruction SHALL instruct the reviewer to verify each `[ ]` item

#### Scenario: Reviewer flags unimplemented AC item as CRITICAL
- **WHEN** the diff contains no implementation evidence for a specific AC item of an assigned requirement
- **THEN** the review prompt instruction SHALL direct the LLM to report:
  `ISSUE: [CRITICAL] REQ-ID: "<ac item>" not implemented in diff`
- **AND** this SHALL be treated as a coverage gap, not a style issue

#### Scenario: Fallback to brief when AC absent
- **WHEN** `build_req_review_section()` runs for a change with requirements that have no `acceptance_criteria`
- **THEN** the function SHALL emit `- REQ-ID: title — brief` (existing behavior)
- **AND** no error is raised

#### Scenario: Cross-cutting REQs unaffected
- **WHEN** rendering the "Cross-Cutting Requirements" section
- **THEN** those REQs SHALL appear with title only, no AC items, unchanged from current behavior
