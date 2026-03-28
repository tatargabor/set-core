# Tasks: docs-rewrite-release

## 1. Archive old docs

- [x] 1.1 Create docs/archive/ directory [REQ: archive-old-docs]
- [x] 1.2 Move prose docs to archive: wt-web.md, ralph.md, getting-started.md, project-setup.md, project-knowledge.md, readme-guide.md, planning-guide.md, plan-checklist.md, memory-seeding-guide.md, benchmark-craftbrew-run1.md, benchmark-minishop-run4.md, kiro-comparison.md, research-ruflo-*.md [REQ: archive-old-docs]
- [x] 1.3 Move docs/research/ to docs/archive/research/ [REQ: archive-old-docs]
- [x] 1.4 Keep in place: howitworks/, images/, specs/, design/, screenshot-pipeline.md, discord-integration.md, gui.md [REQ: archive-old-docs]
- [ ] 1.5 Search-replace all internal doc links that point to archived files [REQ: archive-old-docs]

## 2. Create docs structure

- [x] 2.1 Create directory structure: docs/guide/, docs/reference/, docs/learn/, docs/examples/ [REQ: documentation-hierarchy]
- [x] 2.2 Write docs/INDEX.md — navigation map with reading paths for solo dev, team lead, contributor [REQ: navigation-index]

## 3. Guide section (how-to workflows)

- [x] 3.1 Write docs/guide/quick-start.md — install + first orchestration with screenshots [REQ: documentation-hierarchy]
- [x] 3.2 Write docs/guide/orchestration.md — full orchestration workflow (sentinel → plan → dispatch → gates → merge) with dashboard screenshots [REQ: documentation-hierarchy]
- [x] 3.3 Write docs/guide/sentinel.md — supervisor setup and monitoring [REQ: documentation-hierarchy]
- [x] 3.4 Write docs/guide/worktrees.md — parallel development with set-new/set-work/set-merge [REQ: documentation-hierarchy]
- [x] 3.5 Write docs/guide/openspec.md — spec-driven development workflow (/opsx:* commands) [REQ: documentation-hierarchy]
- [x] 3.6 Write docs/guide/memory.md — persistent memory system with CLI screenshots [REQ: documentation-hierarchy]
- [x] 3.7 Write docs/guide/dashboard.md — web dashboard setup and usage with all tab screenshots [REQ: documentation-hierarchy]
- [x] 3.8 Write docs/guide/team-sync.md — multi-agent coordination [REQ: documentation-hierarchy]

## 4. Reference section (lookup)

- [ ] 4.1 Write docs/reference/cli.md — complete CLI reference with terminal screenshots [REQ: documentation-hierarchy]
- [ ] 4.2 Write docs/reference/configuration.md — all config files and options [REQ: documentation-hierarchy]
- [ ] 4.3 Write docs/reference/architecture.md — technical design, layer model, module system [REQ: documentation-hierarchy]
- [ ] 4.4 Write docs/reference/plugins.md — project type system, creating plugins [REQ: documentation-hierarchy]
- [x] 4.5 Move docs/screenshot-pipeline.md to docs/reference/screenshot-pipeline.md [REQ: documentation-hierarchy]

## 5. Learn section (deep dives)

- [x] 5.1 Write docs/learn/how-it-works.md — overview linking to howitworks/ chapters [REQ: documentation-hierarchy]
- [x] 5.2 Write docs/learn/journey.md — development stats, architecture evolution, milestones [REQ: development-statistics-showcase]
- [x] 5.3 Write docs/learn/benchmarks.md — consolidated benchmark highlights with screenshots (minishop-run4, craftbrew) [REQ: benchmark-highlights]
- [x] 5.4 Write docs/learn/lessons-learned.md — production insights from E2E runs [REQ: lessons-learned]

## 6. Examples

- [ ] 6.1 Write docs/examples/minishop-walkthrough.md — complete E2E example with app screenshots [REQ: documentation-hierarchy]
- [ ] 6.2 Write docs/examples/first-project.md — getting started step-by-step [REQ: documentation-hierarchy]

## 7. README rewrite

- [x] 7.1 Write new README.md — hero + features + quickstart + screenshots + stats + navigation (~200 lines) [REQ: readme-orchestration-first-narrative]
- [ ] 7.2 Add auto-generated screenshots to README (dashboard overview, token chart, app products) [REQ: readme-orchestration-first-narrative]
- [ ] 7.3 Add development stats badge section (commits, specs, LOC) [REQ: readme-orchestration-first-narrative]

## 8. Cross-references and integration

- [ ] 8.1 Add spec-doc cross-reference comments to all guide/ and reference/ pages [REQ: spec-doc-cross-references]
- [ ] 8.2 Add Playwright test report screenshot capture to screenshot pipeline (optional enhancement) [REQ: screenshot-integration]
- [ ] 8.3 Write CONTRIBUTING.md — short, links to architecture + dev setup [REQ: documentation-hierarchy]
- [ ] 8.4 Update docs/howitworks/en/00-meta.md to reference new docs structure [REQ: documentation-hierarchy]

## 9. Validation

- [ ] 9.1 Verify all internal links work (grep for broken references) [REQ: documentation-hierarchy]
- [ ] 9.2 Verify README renders correctly on GitHub (preview) [REQ: readme-orchestration-first-narrative]
- [ ] 9.3 Verify screenshots display in all doc pages [REQ: screenshot-integration]
- [ ] 9.4 Run `make screenshots` to ensure all referenced images exist [REQ: screenshot-integration]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN developer opens README THEN understands purpose in 3 paragraphs with screenshots [REQ: readme-orchestration-first-narrative, scenario: first-time-visitor-understands-purpose-in-30-seconds]
- [ ] AC-2: WHEN README rendered on GitHub THEN under 200 lines [REQ: readme-orchestration-first-narrative, scenario: readme-under-200-lines]
- [ ] AC-3: WHEN user wants first orchestration THEN guide/quick-start.md walks through with screenshots [REQ: documentation-hierarchy, scenario: guide-section-covers-common-workflows]
- [ ] AC-4: WHEN user needs CLI command THEN reference/ has it with all options [REQ: documentation-hierarchy, scenario: reference-section-is-complete]
- [ ] AC-5: WHEN reading journey section THEN sees commits, LOC, specs, E2E runs [REQ: development-statistics-showcase, scenario: stats-section-shows-key-numbers]
- [ ] AC-6: WHEN reading benchmarks THEN minishop results shown with screenshots [REQ: benchmark-highlights, scenario: minishop-benchmark-featured]
- [ ] AC-7: WHEN old docs needed THEN found in docs/archive/ [REQ: archive-old-docs, scenario: old-docs-accessible-but-not-prominent]
- [ ] AC-8: WHEN spec changes THEN grep finds affected docs via cross-references [REQ: spec-doc-cross-references, scenario: spec-change-triggers-doc-update-awareness]
