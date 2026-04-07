# Spec: Design Brief Stem Match

## ADDED Requirements

## IN SCOPE
- Stem-based bidirectional page matching in `design_brief_for_dispatch()`
- Matching as a third layer after exact and alias checks
- Stem function using first 4 characters of each word

## OUT OF SCOPE
- Changing the exact-match or alias-match layers
- Changing `_dispatch_from_design_system()` (already has bidirectional)
- Weighted scoring or ML-based matching
- Modifying how matched page sections are extracted (awk logic)

### Requirement: Stem bidirectional matching
When exact page-name substring matching and alias matching both fail, `design_brief_for_dispatch()` SHALL attempt stem-based bidirectional matching as a third layer.

The algorithm: split the page name into words (3+ characters), stem each to its first 4 characters, and check if ALL stemmed words appear somewhere in the scope text (case-insensitive). A page matches only if every word's stem is found.

#### Scenario: Multi-word page name with all words in scope
- **WHEN** page name is "Admin Products" and scope is "admin product management CRUD table"
- **THEN** match succeeds because stem("admin")="admi" and stem("products")="prod" both appear in the scope

#### Scenario: Multi-word page name with partial words in scope
- **WHEN** page name is "Product Grid" and scope is "admin product management"
- **THEN** match fails because stem("grid")="grid" does not appear in the scope

#### Scenario: Single-word page name
- **WHEN** page name is "Cart" and scope is "shopping cart with checkout flow"
- **THEN** match succeeds because stem("cart")="cart" appears in the scope

#### Scenario: Short words are excluded from stem check
- **WHEN** page name contains words shorter than 3 characters (e.g., articles, prepositions)
- **THEN** those words are skipped and only words with 3+ characters participate in the match

#### Scenario: Stem matching is case-insensitive
- **WHEN** page name is "Admin Dashboard" and scope is "ADMIN panel with DASHBOARD stats"
- **THEN** match succeeds because comparison is case-insensitive

### Requirement: Matching layer priority
The three matching layers SHALL be evaluated in order. Once a layer matches, the page is included and subsequent layers are skipped for that page.

1. Exact: full page name as substring of scope
2. Alias: any alias phrase as substring of scope
3. Stem bidir: all page words (stemmed) found in scope

#### Scenario: Exact match takes priority
- **WHEN** page name "Shopping Cart" appears literally in scope "shopping cart checkout"
- **THEN** the page matches via exact layer and stem layer is not evaluated

#### Scenario: Alias match takes priority over stem
- **WHEN** page has alias "auth" and scope contains "auth flow" but not the full page name
- **THEN** the page matches via alias layer
