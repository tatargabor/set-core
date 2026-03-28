# Proposal: docs-rewrite-release

## Why

The documentation is scattered across 76 files with three competing narratives: README (536 lines, overloaded), howitworks/ (excellent 18-chapter book but hidden), and 15 standalone feature docs (good content, poor organization). Users can't find a clear path from "what is this?" to "how do I use it?" to "how does it work internally?". For the public release this weekend, we need a GitHub-ready documentation structure: concise README, clear navigation, progressive disclosure, and a "development journey" showcase section that demonstrates the system's maturity (1,287 commits, 363 specs, 44K Python LOC, 12K TS LOC, autonomous E2E runs with zero intervention).

## What Changes

- **Rewrite README.md** — trim from 536 to ~200 lines, orchestration-first narrative, auto-generated screenshots, clear navigation to docs/
- **Restructure docs/** — organize into guide/ (workflows), reference/ (lookup), learn/ (deep dives) with a central INDEX.md navigation map
- **Archive old docs** — move current scattered docs to docs/archive/ for reference
- **New "Journey" section** — development history, lessons learned, benchmark highlights extracted from commits and E2E reports
- **Spec-doc references** — link openspec/specs/ capabilities to their documentation sections for future updateability
- **Screenshot integration** — embed auto-generated screenshots from the pipeline throughout the docs
- **Example workflows** — practical "day 1" walkthroughs using minishop and micro-web projects

## Capabilities

### New Capabilities
- `docs-site-structure` — the reorganized documentation hierarchy and navigation system
- `docs-development-journey` — the showcase section with stats, milestones, and lessons

### Modified Capabilities
_(none)_

## Impact

- `README.md` — complete rewrite
- `docs/` — restructured: INDEX.md, guide/, reference/, learn/
- `docs/archive/` — old docs moved here
- Auto-generated screenshots embedded in new docs
- No code changes — documentation only
