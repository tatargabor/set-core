# Spec: Context-Aware Merge

## Requirements

### REQ-CAM-01: Scope injection from orchestrator
merger.py passes the change's scope to wt-merge via `WT_MERGE_SCOPE` environment variable. Truncated to 2000 chars.

### REQ-CAM-02: Structural conflict auto-resolve
Before calling the LLM, auto-resolve delete/modify and rename conflicts using pattern-based rules:
- Delete/modify where feature modified → keep feature version
- Delete/modify where feature deleted → accept deletion
- Rename conflicts in tmp/, .claude/ → accept either side
- Log each auto-resolved file

### REQ-CAM-03: Branch history in LLM prompt
Include `git log --oneline source..target` (max 10 lines each direction) in the LLM conflict resolution prompt to give temporal context.

### REQ-CAM-04: File role hints in LLM prompt
For each conflicted file, add a role hint based on path pattern (test, config, component, schema, etc.) to guide the LLM's resolution strategy.

### REQ-CAM-05: Resolution strategy section
Add a "RESOLUTION STRATEGY" block to the LLM prompt explaining: prefer source for feature code, keep both for additive changes, use target as base for configs.

## Scenarios

### WHEN merger.py calls wt-merge with WT_MERGE_SCOPE set
THEN the LLM prompt contains "What the source branch implemented:" with the scope text
AND the prompt contains source and target branch commit histories

### WHEN a delete/modify conflict occurs on a feature file
THEN auto_resolve_structural_conflicts resolves it without LLM
AND the resolution is logged

### WHEN a content conflict occurs in a test file
THEN the LLM prompt includes "TEST file — prefer source (feature tests)" hint

### WHEN all conflicts are structural (delete/modify + rename)
THEN no LLM call is made
AND merge succeeds automatically
