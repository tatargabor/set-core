## MODIFIED Requirements

### Requirement: Cross-spec DB pollution rule forbids exact-count assertions
The web template testing-conventions file SHALL contain a section titled `Cross-Spec DB Pollution — Exact Counts Forbidden` that explains why `toHaveCount(N)` is unsafe when multiple spec files run against the same dev.db and how to write isolation-safe count assertions.

#### Scenario: Rule content explains the failure mode
- **WHEN** an agent reads the rule
- **THEN** the rule states that Playwright runs specs alphabetically in a single worker with SQLite, and any spec that `CREATE`s rows pollutes the count seen by later specs
- **AND** the rule gives a WRONG example using `await expect(cards).toHaveCount(6)`
- **AND** the rule gives a CORRECT example using `await expect(cards).toHaveCount({ min: 6 })` or scoping the count to a specific test-scoped selector

#### Scenario: Applicability is explicit
- **WHEN** an agent authoring a storefront listing test reads the rule
- **THEN** the rule tells the agent to ban exact-count assertions whenever the counted entity type is also written by any other spec in the same suite
- **AND** the rule recommends using `.filter()` with a unique attribute or `data-testid` to count only the rows the current test knows about

### Requirement: getByLabel prefix-ambiguity rule requires exact: true
The web template testing-conventions file SHALL contain a section titled `getByLabel Prefix Ambiguity — Require exact: true` that explains when `getByLabel` without `{ exact: true }` causes strict-mode violations.

#### Scenario: Rule content explains the failure mode
- **WHEN** an agent reads the rule
- **THEN** the rule states that `getByLabel("Foo")` uses substring matching by default and matches any label whose text contains `"Foo"`
- **AND** the rule gives a WRONG example where `getByLabel("Description")` also matches `"Short Description"` and Playwright throws strict-mode
- **AND** the rule gives a CORRECT example using `getByLabel("Description", { exact: true })`

#### Scenario: When to apply
- **WHEN** an agent writes a test that fills a form with multiple labels sharing a prefix (e.g. `"Name"` + `"Display Name"`, `"Price"` + `"Sale Price"`)
- **THEN** the rule tells the agent to use `{ exact: true }` on every `getByLabel` call whose text is a prefix of another label on the same page

### Requirement: toHaveURL regex exclusion rule
The web template testing-conventions file SHALL contain a section titled `toHaveURL Regex — Exclude Intermediate Routes` that explains how bare substring regex patterns cause login-redirect races.

#### Scenario: Rule content explains the failure mode
- **WHEN** an agent reads the rule
- **THEN** the rule states that `toHaveURL(/\/admin/)` matches `/admin/login` immediately, causing the test to proceed before the actual protected route is reached
- **AND** the rule gives a WRONG example: `await expect(page).toHaveURL(/\/admin/)`
- **AND** the rule gives two CORRECT examples: one with negative lookahead (`toHaveURL(/\/admin(?!\/login)/)`) and one with a specific-path anchor (`toHaveURL(/\/admin\/dashboard/)`)

#### Scenario: Generalization
- **WHEN** an agent writes any post-login assertion using `toHaveURL`
- **THEN** the rule tells the agent to use an exclusion pattern or a specific-path anchor whenever the target path has a login or setup sub-route sharing the same prefix
