## ADDED Requirements

### Requirement: Change-aware query building
The recall hook detects completed changes from git commit history (parsing `change-name: description` format) and builds recall queries from those change names rather than from the raw prompt text.

#### Scenario: 4 of 6 changes committed
- **WHEN** git log contains commits with messages like `product-catalog: ...`, `shopping-cart: ...`, `multi-vendor: ...`, `discounts: ...`
- **AND** no commits exist for `checkout` or `order-workflow`
- **THEN** the recall query SHALL search for memories matching the completed change names extracted from commit messages

#### Scenario: No openspec directory
- **WHEN** the project has no `openspec/` directory
- **THEN** the hook falls back to prompt-based recall (first 200 chars of prompt text)

#### Scenario: No committed changes found
- **WHEN** git log contains no commits matching the `change-name: description` format
- **THEN** the hook falls back to prompt-based recall

### Requirement: Actionable output format
The recall output is formatted as a concise bulleted list with an instruction header, not raw memory JSON.

#### Scenario: Recall returns 3 memories
- **WHEN** 3 memories are found for completed changes
- **THEN** output format is:
  ```
  === PROJECT MEMORY ===
  Previously completed changes — maintain consistency:
  • product-catalog: SQLite+Prisma, images as JSON string, auto-increment IDs
  • shopping-cart: Session-based cart, stock reservation with $transaction
  • multi-vendor: Optional vendorId migration, order split by vendor into SubOrders
  === END ===
  ```

#### Scenario: No memories found
- **WHEN** no memories match the query
- **THEN** no output is produced (silent exit)

### Requirement: Timeout safety
The recall hook must complete within its 15-second timeout even if git log or set-memory recall is slow.

#### Scenario: set-memory recall hangs
- **WHEN** set-memory recall takes >10 seconds
- **THEN** the hook exits silently (killed by Claude Code timeout)
