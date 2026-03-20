# Tasks: Enrich Digest Domains Tab

## 1. Thread digest data to DomainsPanel

- [x] 1.1 Update DomainsPanel props to accept reqs, coverage, dependencies, and ambiguities [REQ: digest-data-threading]
- [x] 1.2 Pass the additional props from DigestView where DomainsPanel is rendered [REQ: digest-data-threading]

## 2. Enrich domain card layout

- [x] 2.1 Add per-domain progress bar (merged/total reqs) at the top of each domain card [REQ: domain-progress-display]
- [x] 2.2 Add domain requirement list with ID, title, change, and status — sortable by status [REQ: domain-requirement-list]
- [x] 2.3 Add AC expand on requirement click, with checkbox rendering [REQ: domain-requirement-list]
- [x] 2.4 Add AC coverage summary (count + percentage + mini progress bar) [REQ: domain-ac-coverage-summary]
- [x] 2.5 Add ambiguity warnings section — filter ambiguities by affected requirements in this domain [REQ: domain-ambiguity-warnings]
- [x] 2.6 Add cross-domain dependency links — compute domain-level edges from requirement-level dependencies, show incoming/outgoing [REQ: cross-domain-dependency-links]
- [x] 2.7 Add source files section — unique source paths from reqs with count per source [REQ: domain-source-files]

## 3. Sidebar progress mini-bars

- [x] 3.1 Add inline progress bar and "N/M" count next to each domain name in desktop sidebar [REQ: sidebar-progress-mini-bars]
- [x] 3.2 Add progress indicator to mobile dropdown domain picker [REQ: sidebar-progress-mini-bars]

## 4. Migrate Dependency Tree to Digest tab

- [x] 4.1 Extract DependencyTree and related components (ProgressBar, STATUS_COLOR, STATUS_TEXT) from ProgressView into shared location or import directly [REQ: requirements-tab-removal]
- [x] 4.2 Add "Dep Tree" sub-tab to DigestView that renders DependencyTree with lazy-loaded requirements data [REQ: requirements-tab-removal]

## 5. Remove Requirements tab

- [x] 5.1 Remove the "requirements" entry from the tabs array in Dashboard.tsx [REQ: requirements-tab-removal]
- [x] 5.2 Remove ProgressView import and rendering from Dashboard.tsx [REQ: requirements-tab-removal]
- [x] 5.3 Remove getRequirements import from Dashboard.tsx if no longer used [REQ: requirements-tab-removal]
- [x] 5.4 Delete web/src/components/ProgressView.tsx [REQ: requirements-tab-removal]

## 6. Build and verify

- [x] 6.1 Run TypeScript build to verify no type errors [REQ: requirements-tab-removal]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a domain has 6 merged and 2 pending requirements THEN the progress bar shows 75% filled with "6/8 merged" text [REQ: domain-progress-display, scenario: domain-with-mixed-status-requirements]
- [x] AC-2: WHEN user selects a domain THEN all requirements are listed with coverage status and assigned change [REQ: domain-requirement-list, scenario: viewing-domain-requirements]
- [x] AC-3: WHEN user clicks a requirement with AC THEN AC items expand inline with checkbox rendering [REQ: domain-requirement-list, scenario: expanding-acceptance-criteria]
- [x] AC-4: WHEN a domain has 19/24 AC items covered THEN summary shows "19/24 AC (79%)" with progress bar [REQ: domain-ac-coverage-summary, scenario: ac-progress-display]
- [x] AC-5: WHEN a domain has related ambiguities THEN warnings are displayed with type badge [REQ: domain-ambiguity-warnings, scenario: domain-with-ambiguities]
- [x] AC-6: WHEN a domain has no ambiguities THEN no ambiguity section renders [REQ: domain-ambiguity-warnings, scenario: domain-without-ambiguities]
- [x] AC-7: WHEN domain "cart" depends on "catalog" and "promotions" THEN outgoing links show both with requirement pairs [REQ: cross-domain-dependency-links, scenario: domain-with-cross-domain-dependencies]
- [x] AC-8: WHEN domain has reqs from multiple source files THEN sources section lists files with counts [REQ: domain-source-files, scenario: domain-sourced-from-multiple-files]
- [x] AC-9: WHEN viewing Domains on desktop THEN each sidebar domain shows mini progress bar and "N/M" [REQ: sidebar-progress-mini-bars, scenario: desktop-sidebar-with-progress]
- [x] AC-10: WHEN viewing dashboard THEN "Requirements" tab no longer appears AND Digest has "Dep Tree" sub-tab [REQ: requirements-tab-removal, scenario: dashboard-tabs-after-change]
