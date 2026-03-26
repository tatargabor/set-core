## fix-target-classification

### Requirements

- REQ-1: Investigation prompt must ask the agent to classify fix_target as "framework", "consumer", or "both"
- REQ-2: `_parse_proposal()` must extract fix_target from proposal "## Fix Target" section
- REQ-3: If no explicit fix_target in proposal, fall back to keyword heuristic (existing behavior)
- REQ-4: Fixer must handle fix_target="both" — framework fix first, deploy, then consumer fix
- REQ-5: fix_target="both" creates change in set-core, deploys via set-project init, then applies local fix

### Scenarios

**framework-bug-detected**
GIVEN investigation finds merger doesn't auto-resolve .claude/** conflicts
WHEN proposal contains "**Target:** framework" with reasoning "affects all projects"
THEN fix_target="framework" and fixer works in set-core

**consumer-bug-detected**
GIVEN investigation finds middleware.ts merge conflict between two changes
WHEN proposal contains "**Target:** consumer" with reasoning "specific to this project"
THEN fix_target="consumer" and fixer works in consumer project

**both-detected**
GIVEN investigation finds template deploys broken seed image URLs
WHEN proposal contains "**Target:** both" with reasoning "template bug + existing broken data"
THEN fixer creates framework fix in set-core AND local fix in consumer

**no-explicit-target-fallback**
GIVEN investigation proposal has no "## Fix Target" section
WHEN _parse_proposal runs
THEN falls back to keyword heuristic (existing framework_indicators logic)
