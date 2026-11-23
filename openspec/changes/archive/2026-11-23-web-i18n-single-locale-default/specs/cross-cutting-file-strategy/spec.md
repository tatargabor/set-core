## MODIFIED Requirements

### Requirement: i18n sidecar pattern for parallel agents
The dispatcher SHALL instruct agents to write i18n keys to per-feature namespace files (e.g., `src/messages/en.<feature>.json`) instead of the canonical merged file in projects with `i18n.mode: multi` (as resolved via `get_i18n_mode(project_path)` from the `web-template-i18n-modes` capability) and legacy projects with no `i18n.mode` declared. Each sidecar file SHALL own one or more top-level namespaces.

In single-mode projects (`i18n.mode: single`), this requirement SHALL NOT apply: the dispatcher SHALL NOT emit i18n sidecar instructions, and agents writing user-visible strings SHALL place them in `src/copy/index.ts` per the `web-template-i18n-modes` capability.

#### Scenario: Agent receives sidecar instructions in multi mode
- **WHEN** a change is dispatched in a multi-mode project that touches i18n keys AND the project uses JSON-based i18n (next-intl, react-intl, or similar)
- **THEN** the dispatch context SHALL instruct the agent to write keys to a feature-specific sidecar file, not the canonical messages file

#### Scenario: Namespace assignment in multi mode
- **WHEN** the planner creates changes in a multi-mode project that each need i18n keys
- **THEN** each change SHALL be assigned specific top-level namespaces (e.g., change "checkout-orders" owns `checkout.*`, `orders.*`) and no two parallel changes SHALL own the same namespace

#### Scenario: Agent writes to sidecar in multi mode
- **WHEN** an agent in a multi-mode project adds i18n keys following dispatch instructions
- **THEN** the keys SHALL be in a separate file that does not conflict with other agents' i18n files at the git level

#### Scenario: Single-mode project receives no sidecar instructions
- **WHEN** a change is dispatched in a single-mode project
- **THEN** the dispatch context SHALL NOT include any i18n sidecar instructions
- **AND** the agent SHALL be directed to add user-visible strings to `src/copy/index.ts` instead

### Requirement: Post-merge i18n combination
The merger SHALL trigger a combination step after merging a branch that contains i18n sidecar files in projects with `i18n.mode: multi` and legacy projects with no `i18n.mode` declared. The combination SHALL merge all per-feature sidecar files into the canonical messages file using top-level `Object.assign` (no deep merge).

In single-mode projects, this requirement SHALL NOT apply (no sidecar files exist to combine).

#### Scenario: Sidecar files merged after branch merge in multi mode
- **WHEN** a branch in a multi-mode project containing `en.<feature>.json` sidecar files is merged to main
- **THEN** the merger SHALL combine all sidecar files into the canonical `en.json` (and other locale files) preserving all namespaces

#### Scenario: No sidecar files present
- **WHEN** the merged branch does not contain i18n sidecar files (regardless of mode)
- **THEN** the merger SHALL skip the combination step without error

#### Scenario: Namespace collision detected in multi mode
- **WHEN** two sidecar files in a multi-mode project define the same top-level namespace key
- **THEN** the combination step SHALL report a warning and use last-write-wins ordering (alphabetical by feature name)

#### Scenario: Single-mode project skips combination step
- **WHEN** a branch in a single-mode project is merged
- **THEN** the merger's i18n combination step SHALL be a no-op (no `messages/` directory exists)

## ADDED Requirements

### Requirement: Single-mode treats `src/copy/index.ts` as a cross-cutting file
In single-mode projects (`i18n.mode: single`), the `src/copy/index.ts` file SHALL be treated as a cross-cutting file for the purpose of ownership assignment and the `cross-cutting-review` directive. The file SHALL be referenced under `cross_cutting_files.i18n` in `project-knowledge.yaml` rather than `messages/*.json`.

#### Scenario: Single-mode project knowledge points at copy module
- **GIVEN** a single-mode project initialized via `set-project init --i18n single`
- **WHEN** `project-knowledge.yaml` is inspected
- **THEN** `cross_cutting_files.i18n` SHALL be `["src/copy/index.ts", "src/copy/locale.ts"]`

#### Scenario: Multi-mode project knowledge points at messages
- **GIVEN** a multi-mode project initialized via `set-project init --i18n multi`
- **WHEN** `project-knowledge.yaml` is inspected
- **THEN** `cross_cutting_files.i18n` SHALL be `["messages/*.json"]`

#### Scenario: Cross-cutting-review fires on copy edits in single mode
- **WHEN** a change in a single-mode project modifies `src/copy/index.ts`
- **THEN** the `cross-cutting-review` directive SHALL flag the change for extra review (because the file is listed in `cross_cutting_files.i18n`)

#### Scenario: Planner serializes copy-module edits in single mode
- **WHEN** multiple changes in a single-mode project's planning round all need to modify `src/copy/index.ts`
- **THEN** the planner SHALL apply the existing cross-cutting ownership rule (one owner, others receive `depends_on`) — the same mechanism that applies to `layout.tsx`, `middleware.ts`, etc.
