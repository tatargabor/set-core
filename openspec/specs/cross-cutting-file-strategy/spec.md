## ADDED Requirements

### Requirement: i18n sidecar pattern for parallel agents
The dispatcher SHALL instruct agents to write i18n keys to per-feature namespace files (e.g., `src/messages/en.<feature>.json`) instead of the canonical merged file. Each sidecar file SHALL own one or more top-level namespaces.

#### Scenario: Agent receives sidecar instructions
- **WHEN** a change is dispatched that touches i18n keys AND the project uses JSON-based i18n (next-intl, react-intl, or similar)
- **THEN** the dispatch context SHALL instruct the agent to write keys to a feature-specific sidecar file, not the canonical messages file

#### Scenario: Namespace assignment
- **WHEN** the planner creates changes that each need i18n keys
- **THEN** each change SHALL be assigned specific top-level namespaces (e.g., change "checkout-orders" owns `checkout.*`, `orders.*`) and no two parallel changes SHALL own the same namespace

#### Scenario: Agent writes to sidecar
- **WHEN** an agent adds i18n keys following dispatch instructions
- **THEN** the keys SHALL be in a separate file that does not conflict with other agents' i18n files at the git level

### Requirement: Post-merge i18n combination
The merger SHALL trigger a combination step after merging a branch that contains i18n sidecar files. The combination SHALL merge all per-feature sidecar files into the canonical messages file using top-level `Object.assign` (no deep merge).

#### Scenario: Sidecar files merged after branch merge
- **WHEN** a branch containing `en.<feature>.json` sidecar files is merged to main
- **THEN** the merger SHALL combine all sidecar files into the canonical `en.json` (and other locale files) preserving all namespaces

#### Scenario: No sidecar files present
- **WHEN** the merged branch does not contain i18n sidecar files
- **THEN** the merger SHALL skip the combination step without error

#### Scenario: Namespace collision detected
- **WHEN** two sidecar files define the same top-level namespace key
- **THEN** the combination step SHALL report a warning and use last-write-wins ordering (alphabetical by feature name)

### Requirement: Cross-cutting file ownership in planner
The planner SHALL assign ownership of unsplittable cross-cutting files (layout.tsx, middleware.ts, next.config.js) to at most one change per planning round. Other changes that need to modify these files SHALL receive a `depends_on` constraint.

#### Scenario: Single owner assigned
- **WHEN** multiple changes in a planning round need to modify `layout.tsx`
- **THEN** the planner SHALL assign ownership to one change and add `depends_on` to the others, serializing access

#### Scenario: Non-owner cannot modify owned file
- **WHEN** a change does not own a cross-cutting file
- **THEN** the dispatch context SHALL include "DO NOT modify [file]" for each file owned by another change

#### Scenario: No contention
- **WHEN** only one change needs to modify a cross-cutting file
- **THEN** that change SHALL be assigned ownership without `depends_on` constraints

### Requirement: Cross-cutting files detected from project knowledge
The list of cross-cutting files SHALL be read from `project-knowledge.yaml` (if present) or detected heuristically (files modified by 2+ changes in previous orchestration runs).

#### Scenario: project-knowledge.yaml defines cross-cutting files
- **WHEN** `project-knowledge.yaml` contains a `cross_cutting_files` list
- **THEN** the planner SHALL use that list for ownership assignment

#### Scenario: Heuristic detection
- **WHEN** no explicit cross-cutting file list exists AND orchestration history shows a file was modified by multiple changes
- **THEN** the planner SHALL flag that file as cross-cutting for future rounds
