## Requirements
### Requirement: Agent-assisted merge conflict resolution
**STATUS: ASPIRATIONAL** — This feature is designed but not yet implemented in the orchestrator. The spec is retained as a backlog item. Currently, merge conflicts are handled by the multi-layer auto-resolution in `set-merge` (generated files, package.json, JSON deep merge, LLM resolution).

The orchestrator SHALL attempt agent-assisted rebase before declaring a merge permanently blocked. On the first merge conflict for a change, the orchestrator SHALL launch a Ralph agent in the worktree with instructions to merge the main branch and resolve conflicts.

#### Scenario: First merge conflict triggers agent rebase
- **WHEN** `merge_change()` fails due to merge conflict
- **AND** `agent_rebase_done` is false for the change
- **THEN** the orchestrator SHALL set `agent_rebase_done` to true
- **AND** set `merge_rebase_pending` to true
- **AND** create a `retry_context` with instructions: "Merge conflict: your branch conflicts with {main_branch}. Resolve the conflict by merging {main_branch} into your branch."
- **AND** call `resume_change()` to launch an agent

#### Scenario: Agent rebase completes successfully
- **WHEN** a change with `merge_rebase_pending = true` completes (Ralph done)
- **THEN** `handle_change_done()` SHALL skip the verify gate
- **AND** perform a dry-run merge test using `git merge-tree`
- **AND** if the branch merges cleanly, call `merge_change()` directly

#### Scenario: Agent rebase does not fully resolve conflict
- **WHEN** a change returns from agent rebase
- **AND** the dry-run merge test still shows conflicts
- **THEN** the orchestrator SHALL increment `merge_retry_count`
- **AND** set status to `merge-blocked`
- **AND** the change enters the normal retry merge queue

#### Scenario: Second and subsequent merge conflicts skip agent rebase
- **WHEN** `merge_change()` fails due to merge conflict
- **AND** `agent_rebase_done` is already true
- **THEN** the orchestrator SHALL set status to `merge-blocked` directly
- **AND** NOT launch another agent rebase

### Requirement: Agent rebase memory context
**STATUS: ASPIRATIONAL** — Not yet implemented.

The orchestrator SHALL enrich the agent rebase prompt with relevant memories about recent merges.

#### Scenario: Memory recall for merge context
- **WHEN** constructing the agent rebase retry_context
- **THEN** the orchestrator SHALL call `orch_recall` with query "{change_name} merge conflict recent merges" (limit 3)
- **AND** append any results as a "Context from Memory" section (max 1000 chars)
