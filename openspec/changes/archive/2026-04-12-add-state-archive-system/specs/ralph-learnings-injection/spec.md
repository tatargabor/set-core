## ADDED Requirements

### Requirement: Ralph loop regenerates input.md on iteration transition
The dispatcher SHALL regenerate `input.md` for a change before each ralph iteration when the underlying review learnings checklist has been updated since the previous iteration's input was written. Currently `input.md` is written ONCE by `_build_input_content()` at initial dispatch; subsequent ralph iterations reuse the same file, so learnings persisted from a prior change's merge never reach a change that was already dispatched.

Observed on minishop-run-20260412-0103: after auth-navigation merged and wrote new review learnings (Edge Runtime rule, open admin registration pattern), the in-flight `product-catalog` change was still using its original `input.md` from its first dispatch 40 minutes earlier. The ralph main agent never saw the new learnings. The reviewer did (learnings are injected into the review prompt separately at `verifier.py:2572`), so the reviewer correctly flagged new issues the agent could have prevented — but that's reactive, not preventative.

#### Scenario: Learnings update while change is in ralph loop
- **WHEN** `product-catalog` is actively running its ralph iteration 2 (dispatched at 12:05, currently at 12:35)
- **WHEN** `auth-navigation` merges at 12:20 and writes new learnings at `<project>/set/orchestration/review-learnings.jsonl` with an updated mtime
- **WHEN** the ralph loop completes iteration 2 at 12:40 and is about to start iteration 3
- **THEN** the dispatcher detects that `review-learnings.jsonl` has a newer mtime than `product-catalog/input.md`
- **THEN** the dispatcher regenerates `input.md` using the current learnings checklist
- **THEN** the agent's next ralph iteration sees the updated "Review Learnings Checklist (review will BLOCK if violated)" section

#### Scenario: No learnings update since last iteration
- **WHEN** a change's ralph iteration ends and the learnings file's mtime is OLDER than `input.md`
- **THEN** the dispatcher does NOT regenerate `input.md`
- **THEN** the agent continues using the existing file
- **THEN** no redundant work is done

#### Scenario: First iteration always gets fresh input
- **WHEN** a change is initially dispatched (iteration 1)
- **THEN** `input.md` is generated fresh from the current learnings state
- **THEN** this is the same behavior as today's dispatcher — the new requirement only changes behavior for iterations 2+

### Requirement: Supervisor restart preserves and refreshes input context
When the supervisor daemon restarts and the orchestrator reattaches to an in-flight change's existing worktree (rather than discarding and re-dispatching), the dispatcher SHALL regenerate `input.md` for that change so any learnings, cross-cutting restrictions, or sibling context written during the downtime are surfaced.

Observed same-run: the product-catalog worktree was renamed to `wt-product-catalog-2` and re-dispatched, which DID generate a fresh input.md — but only because the engine's reattach logic chose the full re-dispatch path. The reattach-vs-redispatch decision is currently binary; a mid-path "refresh input only" option does not exist. Adding it aligns with the ralph-iteration refresh above.

#### Scenario: Supervisor restart with change in `running` status
- **WHEN** the supervisor daemon is killed while `product-catalog.status = running` and its worktree still exists with an active `loop-state.json`
- **WHEN** a new daemon starts, the orchestrator reattaches to the existing worktree (no worktree suffix rename)
- **THEN** the dispatcher regenerates `input.md` using the current project state (learnings, state.json, cross-cutting info)
- **THEN** the ralph loop's next iteration reads the refreshed input
- **THEN** no in-flight work is discarded

#### Scenario: Worktree missing on restart
- **WHEN** the supervisor restarts and the change's worktree path no longer exists on disk
- **THEN** current behavior is preserved (full re-dispatch with a new worktree)
- **THEN** the new input.md is generated from scratch as today

### Requirement: Cross-change review learnings file is append-only
The existing `<project>/set/orchestration/review-learnings.jsonl` file SHALL remain append-only. The refresh mechanism above reads the file fresh on every input.md regeneration; it does NOT mutate the file. Deduplication is handled by the existing semantic dedup pipeline in `profile_types.py::_dedup_learnings`.

#### Scenario: Two changes merge in quick succession
- **WHEN** change A merges at 12:20 appending 3 new learnings
- **WHEN** change B (running since 12:05) regenerates its input.md at 12:22 between iterations
- **THEN** the new input.md includes all 3 learnings from A
- **WHEN** change C merges at 12:25 appending 2 more learnings
- **WHEN** change B regenerates input.md again at 12:27 before iteration 3
- **THEN** the new input.md includes all 5 learnings from A and C combined

### Requirement: Refresh is opt-out safe
The dispatcher SHALL log at INFO level every input.md regeneration with the change name, iteration number, and mtime delta. The feature SHALL be disableable via a `refresh_input_on_learnings_update: bool = True` directive in orchestration config.

#### Scenario: Operator disables the feature
- **WHEN** `refresh_input_on_learnings_update: false` is set in the project's directives
- **THEN** the dispatcher never regenerates input.md after initial dispatch
- **THEN** all ralph iterations use the original file (pre-fix behavior)
