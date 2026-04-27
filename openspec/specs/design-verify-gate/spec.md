# Design Verify Gate Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Design compliance section in code review

The verifier SHALL include a design compliance section in the code review prompt when a `design-snapshot.md` exists in the project.

#### Scenario: Review with design snapshot
- **WHEN** `review_change()` runs for a change
- **AND** `design-snapshot.md` exists in the project root
- **THEN** the review prompt includes a "Design Compliance Check" section
- **AND** the section contains the Design Tokens from the snapshot (colors, typography, spacing)
- **AND** instructs the reviewer to compare Tailwind classes in the diff against design token values

#### Scenario: Review without design snapshot
- **WHEN** `review_change()` runs for a change
- **AND** no `design-snapshot.md` exists
- **THEN** no design compliance section is added to the review prompt
- **AND** the review proceeds as before

### Requirement: Design compliance severity

Design compliance issues SHALL be reported as WARNING severity, not CRITICAL. They SHALL NOT block merging.

#### Scenario: Design token mismatch detected
- **WHEN** the reviewer finds that a diff uses `bg-primary` (mapped to #030213/near-black)
- **AND** the design tokens specify interactive elements should use `bg-blue-600`
- **THEN** the reviewer reports: `ISSUE: [WARNING] Design token mismatch — diff uses primary (#030213) but design specifies blue-600 for interactive elements`

#### Scenario: Typography size mismatch
- **WHEN** the reviewer finds `text-2xl` in the diff for a heading
- **AND** the design tokens specify `text-3xl` for that heading level
- **THEN** the reviewer reports a WARNING with the expected vs actual sizes

#### Scenario: Design warning does not block merge
- **WHEN** the review contains design WARNINGs but no CRITICAL issues
- **THEN** the verify gate passes (returns 0)
- **AND** the warnings are logged for visibility

### Requirement: Design token extraction for review

The system SHALL extract a concise token summary from `design-snapshot.md` for the review prompt, limited to actionable design tokens.

#### Scenario: Token extraction content
- **WHEN** design tokens are extracted for the review prompt
- **THEN** the extraction includes: primary colors (background, foreground, primary, destructive, accent), border-radius values, typography scale (h1-h4 sizes and weights), and shadow definitions
- **AND** excludes chart colors, sidebar colors, and other non-UI-critical tokens

#### Scenario: Token extraction size
- **WHEN** the design snapshot contains 50+ design tokens
- **THEN** the extracted token summary for review is limited to the 15-20 most UI-critical tokens

### Requirement: Design review includes component structure checks
The `build_design_review_section()` SHALL include a "Component Structure" subsection when Figma source files are available. This subsection SHALL list key UI patterns found in source files: icon imports, image dimensions, layout containers. The reviewer SHALL compare these against the diff and report mismatches as [WARNING].

#### Scenario: Source files show ShoppingBag icon for cart
- **WHEN** Figma source `Navbar.tsx` imports `ShoppingBag` from lucide-react for the cart link
- **AND** the diff uses text "Cart" without any icon
- **THEN** the review SHALL report: `[WARNING] Design uses ShoppingBag icon for cart nav — implementation uses plain text`

#### Scenario: Source files show product thumbnail in admin table
- **WHEN** Figma source `AdminProducts.tsx` renders `w-12 h-12` image thumbnails in the product table
- **AND** the diff has a product table without image column
- **THEN** the review SHALL report: `[WARNING] Design includes product thumbnail (w-12 h-12) in admin table — implementation omits image`

#### Scenario: No source files available
- **WHEN** no `docs/figma-raw/*/sources/` directory exists
- **THEN** the review section SHALL contain only token checks (existing behavior unchanged)

### Requirement: Icon usage checklist extraction
The bridge SHALL parse Figma source files for lucide-react icon imports and build a checklist of "Component -> Icon" mappings. This checklist SHALL be appended to the review section.

#### Scenario: Multiple icons across source files
- **WHEN** source files contain `import { ShoppingBag, Package, Pencil, Trash2, Plus } from 'lucide-react'`
- **THEN** the review section SHALL include an "Icon Usage" checklist listing each icon and which component uses it

### Requirement: Design review severity remains WARNING
All component structure mismatches SHALL be reported as [WARNING], not [CRITICAL]. Design compliance is advisory — functional correctness takes priority.

#### Scenario: Multiple structure mismatches found
- **WHEN** 3 component structure mismatches are found (missing icon, missing thumbnail, wrong heading size)
- **THEN** all three SHALL be reported as [WARNING]
- **AND** the review SHALL NOT fail the gate
