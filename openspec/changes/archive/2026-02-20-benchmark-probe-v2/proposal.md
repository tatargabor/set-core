## Why

MemoryProbe v1 only tests convention compliance (format, naming patterns) — 2 out of 5 real-world memory categories. The CraftBazaar full benchmark is too expensive (~5M tokens) and shows no memory advantage because most traps are code-readable. We need a benchmark that tests **all 5 categories of cross-session knowledge** in ~35 minutes with ~400K tokens.

## What Changes

- Redesign MemoryProbe change definitions (C01-C05) to include 5 trap categories instead of 2
- Add new trap types: debug knowledge (C), architecture decisions (D), stakeholder constraints (E)
- Redesign C02 "Developer Notes" to plant knowledge across all 5 categories
- Update C03-C05 to probe all 5 categories with traps that are invisible in code
- Rewrite test scripts (test-01.sh through test-05.sh) with new probes (~30+ total)
- Update scoring script with weighted categories (A:x1, B:x2, C:x3, D:x2, E:x3)
- Update project-spec.md, CLAUDE.md variants, init.sh, run.sh, score.sh, run-guide.md

## Capabilities

### New Capabilities
- `probe-categories`: Define the 5 trap categories (convention, human-override, debug-knowledge, architecture-decision, stakeholder-constraint) with scoring weights and probe design principles
- `change-definitions`: Redesigned C01-C05 change files with multi-category traps embedded in C02 Developer Notes
- `scoring-system`: Updated scoring with 5 weighted categories, ~30+ probes, automated bash-based verification

### Modified Capabilities

## Impact

- `benchmark/synthetic/` — All files: project-spec.md, changes/*.md, tests/*.sh, scripts/*.sh, claude-md/*.md, run-guide.md
- No impact on main set-core code — benchmark-only changes
- Backward incompatible with MemoryProbe v1 scoring (new categories, new weights)
