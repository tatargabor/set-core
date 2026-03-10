# Merge and Delivery

## Merge Queue

When a change successfully passes all quality gates, it enters the merge queue. The queue is processed according to the `merge_policy` directive.

![The merge pipeline and post-merge flow](diagrams/rendered/08-merge-pipeline.png){width=90%}

## Merge Policy

Three merge policies exist:

### eager

The change is merged immediately as soon as it reaches the end of the verify pipeline.

```yaml
merge_policy: eager
```

Advantage: fast delivery, other worktrees get fresh main sooner.
Disadvantage: no opportunity for batch review.

### checkpoint (default)

After N changes, the system stops and requests human approval.

```yaml
merge_policy: checkpoint
checkpoint_every: 3
```

Process:

1. The 3rd change completes → checkpoint activates
2. The orchestrator stops (status: `checkpoint`)
3. The human reviews the merge queue
4. `wt-orchestrate approve --merge` → merge + continue

### manual

Every merge requires human approval.

```yaml
merge_policy: manual
```

## The Merge Process

`merge_change()` handles three cases:

### Case 1: Branch No Longer Exists

If the `change/<name>` branch no longer exists (someone manually merged and deleted it):

- Status → `merged`
- Worktree cleanup
- Change archival

### Case 2: Branch Already Merged

If the branch exists but is already an ancestor of HEAD:

- Status → `merged`
- Cleanup

### Case 3: Normal Merge (the common case)

The `wt-merge` command performs the actual merge:

```bash
wt-merge <change-name> --no-push --llm-resolve
```

## 3-Layer Conflict Resolution

In case of merge conflicts, the system attempts resolution at three levels:

### Layer 1: Generated Files (automatic)

`sync_worktree_with_main()` and the merge logic automatically handle generated file conflicts:

- `package-lock.json`
- `yarn.lock`, `pnpm-lock.yaml`
- `*.tsbuildinfo`

These are resolved with `--ours` strategy (the worktree version wins).

### Layer 2: LLM Merge (`--llm-resolve`)

If there is a real code conflict, `wt-merge --llm-resolve` calls a Claude agent:

1. The conflicted files are passed to the LLM
2. The LLM understands the intent of both sides
3. The LLM merges the changes
4. The result is committed

### Layer 3: Human Intervention

If the LLM cannot resolve the conflict either:

- The change moves to `merge_blocked` status
- Notification sent
- The human performs a manual merge
- The orchestrator detects the new state on the next poll

## Post-Merge Pipeline

After a successful merge, the following steps run:

### 1. Running Worktree Synchronization

`_sync_running_worktrees()` ensures that other active worktrees receive the fresh main:

```
main ← merge(auth-system)
  ↓ sync
  worktree/user-profile ← git merge main
  worktree/api-endpoints ← git merge main
```

This prevents other agents from building on stale code.

### 2. Base Build Check

After merge, the base build cache is invalidated (`BASE_BUILD_STATUS=""`), and the next verify gate rechecks that the main branch is buildable.

### 3. Post-Merge Command

If a `post_merge_command` is configured:

```yaml
post_merge_command: "pnpm db:generate"
```

This command runs in the project root after merge. Typical uses:

- Database migration generation (`prisma generate`, `drizzle-kit generate`)
- Build artifact refresh
- Cache invalidation

### 4. Change Archival

`archive_change()` moves the OpenSpec change directory to the archive:

```
openspec/changes/auth-system/
  → openspec/changes/archive/2026-03-10-auth-system/
```

### 5. Post-Merge Hook

If a `hook_post_merge` is configured, it runs with the change name as argument.

### 6. Coverage Update

`update_coverage_status()` updates requirement coverage: the REQ-XXX identifiers assigned to the change move to `merged` status.

## Checkpoint and Approval

### Checkpoint Activation

Checkpoints activate in the following cases:

| Trigger | Description |
|---------|-------------|
| `checkpoint_every: N` | After N merges |
| `token_hard_limit` | Token hard limit reached |
| Manual | `wt-orchestrate pause --all` |

### Approval Process

```bash
wt-orchestrate approve            # approve, continue
wt-orchestrate approve --merge    # approve + immediate merge flush
```

The `--merge` flag immediately merges changes waiting in the merge queue.

### Auto-approve (for E2E runs)

```yaml
checkpoint_auto_approve: true
```

This is used for unsupervised runs (e.g., CI/CD, E2E testing).

\begin{keypoint}
The merge policy should be tuned to the project and team needs. For small projects, the eager policy is most efficient. For larger projects, the checkpoint policy ensures humans see the results before too many changes are merged.
\end{keypoint}

## Merge Retry Intelligence

If a merge fails (e.g., build error after merge), the system:

1. Saves the build output (`build_output`)
2. Moves the change to `merge_blocked` status
3. Retries on the next poll
4. If `fix_base_build_with_llm()` is available, attempts to fix the error with LLM
