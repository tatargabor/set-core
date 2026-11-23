## REMOVED Requirements

### Requirement: IKP context in decomposition prompt
**Reason**: A usage audit found the knowledge-pack bridge loaded by no live entry point — only by the orchestration planner, dispatcher, verifier and templates, which have not run in 30 days — so it is dead code with live import paths.
**Migration**: None needed. A project that wants per-change context puts it in its own rules or its OpenSpec config `context:`.

### Requirement: Planner assigns ikp_packs per change
**Reason**: A usage audit found the knowledge-pack bridge loaded by no live entry point — only by the orchestration planner, dispatcher, verifier and templates, which have not run in 30 days — so it is dead code with live import paths.
**Migration**: None needed. A project that wants per-change context puts it in its own rules or its OpenSpec config `context:`.

### Requirement: Fallback pack assignment
**Reason**: A usage audit found the knowledge-pack bridge loaded by no live entry point — only by the orchestration planner, dispatcher, verifier and templates, which have not run in 30 days — so it is dead code with live import paths.
**Migration**: None needed. A project that wants per-change context puts it in its own rules or its OpenSpec config `context:`.

