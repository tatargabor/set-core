# Design: docs-rewrite-release

## Context

set-core has 76 doc files across docs/, howitworks/, and README. The content quality is high (especially howitworks/ chapters) but the organization is poor — three competing narratives, no clear navigation, and the README tries to do everything at once (536 lines). For the public release, we need a GitHub-ready structure that makes set-core look as professional as it is.

### What we have (reusable)
- **howitworks/** — 18-chapter technical book, excellent quality, keep as-is
- **benchmark reports** — minishop-run4, craftbrew-run1 with real metrics
- **cli-reference.md** — complete command reference
- **screenshot pipeline** — 30+ auto-generated PNGs (dashboard, CLI, app)
- **readme-guide.md** — meta-rules for README generation

### What's bad (fix)
- README overloaded (536 lines → target 200)
- No navigation index
- Feature docs scattered, overlapping with howitworks/
- No showcase/journey section

## Goals / Non-Goals

**Goals:**
- README under 200 lines, orchestration-first, with screenshots
- Clear 3-tier docs hierarchy (guide → reference → learn)
- Development journey showcase with hard numbers
- Spec-doc references for maintainability
- Weekend release-ready

**Non-Goals:**
- Docs website (mkdocs/docusaurus) — later
- Hungarian translation of new content
- Rewriting howitworks/ chapters

## Decisions

### D1: Documentation structure
```
README.md                          (~200 lines)
docs/
├── INDEX.md                       (navigation map)
├── guide/
│   ├── quick-start.md             (install + first orchestration)
│   ├── orchestration.md           (full orchestration workflow)
│   ├── sentinel.md                (supervisor setup)
│   ├── worktrees.md               (parallel development)
│   ├── openspec.md                (spec-driven workflow)
│   ├── memory.md                  (persistent memory)
│   ├── dashboard.md               (web UI)
│   └── team-sync.md               (multi-agent)
├── reference/
│   ├── cli.md                     (all commands)
│   ├── configuration.md           (config files)
│   ├── architecture.md            (technical design)
│   ├── plugins.md                 (project types)
│   └── screenshot-pipeline.md     (already exists)
├── learn/
│   ├── how-it-works.md            (overview + links to howitworks/)
│   ├── journey.md                 (development stats + evolution)
│   ├── benchmarks.md              (consolidated benchmark highlights)
│   └── lessons-learned.md         (production insights)
├── examples/
│   ├── minishop-walkthrough.md    (complete E2E example)
│   └── first-project.md           (getting started example)
├── howitworks/                    (keep as-is, referenced from learn/)
├── images/                        (keep as-is)
└── archive/                       (old docs moved here)
```

**Why:** Three tiers match how users consume docs: "show me how" (guide), "look up X" (reference), "explain why" (learn). howitworks/ stays untouched — it's excellent and already structured.

### D2: README structure
```
1. Hero: one-liner + problem statement + key screenshot
2. What It Does: 6-bullet feature list with icons
3. Quick Start: 3-command getting started
4. The Result: before/after or dashboard + app screenshots
5. Documentation: links to guide/, reference/, learn/
6. Development: key stats (commits, specs, LOC) + link to journey
7. License + Contributing
```

**Why:** Follows the pattern of high-star GitHub projects: hook → features → quickstart → proof → navigation.

### D3: What to archive
Move to docs/archive/:
- `wt-web.md` (replaced by guide/dashboard.md)
- `ralph.md` (merged into guide/orchestration.md)
- `getting-started.md` (replaced by guide/quick-start.md)
- `project-setup.md` (merged into quick-start)
- `project-knowledge.md` (internal)
- `readme-guide.md` (internal meta)
- `planning-guide.md` (internal)
- `plan-checklist.md` (internal)
- `memory-seeding-guide.md` (internal)
- `pm-guide-*.md` if any (internal)
- `benchmark-*.md` (consolidated into learn/benchmarks.md)
- `research/` (internal research)
- `kiro-comparison.md` (outdated comparison)
- `research-ruflo-*.md` (internal)

**NOT archived (stays):**
- `howitworks/` — excellent, referenced from learn/
- `images/` — screenshots
- `screenshot-pipeline.md` — moves to reference/
- `specs/` — internal reference
- `design/` — internal reference
- `discord-integration.md` — active feature doc

### D4: Spec-doc cross-references
Each guide/reference page ends with a hidden HTML comment listing the openspec specs it covers:
```markdown
<!-- specs: orchestration-engine, dispatch-core, verify-gate -->
```
A simple `grep -r "specs:.*verify-gate" docs/` finds all docs that reference a spec.

**Why:** Lightweight, no tooling needed, grep-able. When a spec changes, developers can find affected docs instantly.

### D5: Journey section content
Extract from git history + benchmarks:
- **Timeline**: key milestones with dates (worktree tools → orchestration → sentinel → gates → dashboard → release)
- **Stats table**: commits, LOC, specs, E2E runs, tests
- **Benchmark card**: minishop-run4 (6/6, zero intervention, 1h45m) with dashboard + app screenshots
- **Lessons list**: 5-7 key insights from production runs (one paragraph each)

**Why:** Shows maturity and real-world testing — not a prototype but a battle-tested system.

## Risks / Trade-offs

- [Risk] Breaking internal doc links → Mitigation: search-replace all references, test with grep
- [Risk] Archive losing git blame → Mitigation: `git mv` preserves history
- [Risk] Content duplication between guide/ and howitworks/ → Mitigation: guide/ is concise how-to, howitworks/ is deep-dive; guide links to howitworks/ for details
- [Risk] Weekend deadline pressure → Mitigation: parallelize with multiple agents; guide/ is highest priority, learn/ and examples/ can follow

## Open Questions

- Should we add a CONTRIBUTING.md? **Recommendation:** Yes, short one linking to docs/reference/architecture.md
