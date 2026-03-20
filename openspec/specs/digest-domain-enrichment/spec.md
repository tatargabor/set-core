# digest-domain-enrichment Specification

## Purpose
TBD - created by archiving change enrich-digest-domains. Update Purpose after archive.
## Requirements
### Requirement: Domain progress display
Each domain card SHALL display a progress bar showing the ratio of merged/done requirements to total requirements in that domain. The progress bar SHALL use the same color scheme as existing progress bars (blue for done, green for in-progress, red for failed).

#### Scenario: Domain with mixed status requirements
- **WHEN** a domain has 6 merged and 2 pending requirements
- **THEN** the progress bar shows 75% filled in blue with "6/8 merged" text

### Requirement: Domain requirement list
Each domain card SHALL display a list of all requirements belonging to that domain, showing requirement ID, title, assigned change name, and coverage status. Requirements SHALL be sorted with active/failed first, then pending, then completed.

#### Scenario: Viewing domain requirements
- **WHEN** user selects a domain
- **THEN** all requirements for that domain are listed with their coverage status and assigned change

#### Scenario: Expanding acceptance criteria
- **WHEN** user clicks on a requirement that has acceptance criteria
- **THEN** the AC items expand inline with checkbox-style rendering (checked if requirement is done)

### Requirement: Domain AC coverage summary
Each domain card SHALL display an acceptance criteria coverage summary showing the count and percentage of AC items that are covered (requirement merged/done).

#### Scenario: AC progress display
- **WHEN** a domain has 19 covered AC items out of 24 total
- **THEN** the summary shows "19/24 AC (79%)" with a progress bar

### Requirement: Domain ambiguity warnings
Each domain card SHALL display any ambiguities from the digest that affect requirements in that domain. Ambiguities SHALL be shown with their type (underspecified, contradictory, missing_reference, implicit_assumption) and description.

#### Scenario: Domain with ambiguities
- **WHEN** a domain has requirements referenced in the ambiguities data
- **THEN** the ambiguity warnings are displayed with a warning icon and type badge

#### Scenario: Domain without ambiguities
- **WHEN** a domain has no related ambiguities
- **THEN** no ambiguity section is rendered

### Requirement: Cross-domain dependency links
Each domain card SHALL display incoming and outgoing dependency links to other domains, derived from the requirement-level dependencies data. Links SHALL be grouped by direction (incoming: other domains depend on this one; outgoing: this domain depends on others).

#### Scenario: Domain with cross-domain dependencies
- **WHEN** domain "cart" has requirements that depend on requirements in "catalog" and "promotions"
- **THEN** outgoing links show "catalog" and "promotions" with the specific requirement pairs

### Requirement: Domain source files
Each domain card SHALL list the unique spec source files that its requirements originate from, with a count of requirements per source file.

#### Scenario: Domain sourced from multiple files
- **WHEN** domain "catalog" has requirements from "features/product-catalog.md" (6 reqs) and "features/homepage.md" (2 reqs)
- **THEN** the sources section lists both files with their counts

### Requirement: Sidebar progress mini-bars
The domain sidebar (desktop) and dropdown picker (mobile) SHALL display a mini progress bar next to each domain name, showing the merged/total ratio. Fully completed domains SHALL show a completion indicator.

#### Scenario: Desktop sidebar with progress
- **WHEN** viewing the Domains sub-tab on desktop
- **THEN** each domain in the sidebar shows a small inline progress bar and "N/M" count

### Requirement: Requirements tab removal
The standalone Requirements tab (ProgressView component) SHALL be removed from the dashboard. The Dependency Tree view SHALL be preserved as a new sub-tab within the Digest tab.

#### Scenario: Dashboard tabs after change
- **WHEN** viewing the dashboard
- **THEN** the "Requirements" tab no longer appears in the tab bar
- **THEN** the Digest tab contains a "Dep Tree" sub-tab with the change-level dependency visualization

### Requirement: Digest data threading
The DomainsPanel component SHALL receive the full digest data (requirements, coverage, dependencies, ambiguities) as props, not just the domain markdown summaries. This data SHALL be cross-referenced to build the enriched domain cards.

#### Scenario: Data flow
- **WHEN** the DigestView renders the DomainsPanel
- **THEN** it passes reqs, coverage, dependencies, and ambiguities alongside the domain summaries

