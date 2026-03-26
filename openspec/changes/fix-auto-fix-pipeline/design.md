## State Machine Simplification

The fix agent (`/opsx:apply`) handles implement + test + commit + archive in one shot. No separate verify or deploy step needed.

```
NEW → INVESTIGATING → DIAGNOSED → [AWAITING_APPROVAL →] FIXING → RESOLVED
                                                          ↓
                                                        FAILED → retry → INVESTIGATING
```

VERIFYING and DEPLOYING states kept in enum for backwards compat but treated as pass-through to RESOLVED in the tick handler.

## Filesystem-Based Success Detection

When `fixer.collect()` is called but the in-memory process reference is lost (service restart, sentinel interference), fall back to checking the filesystem:

1. Is the openspec change archived? (`openspec/changes/archive/*{change_name}*` exists and `openspec/changes/{change_name}` does not)
2. Is the fix agent PID still alive? (`os.kill(pid, 0)`)

Same pattern for `investigator.collect()` — check if `proposal.md` exists on disk.

## Finding-Pipeline Sync

When the issue pipeline picks up a finding:
1. `DetectionBridge` marks the finding status as `"pipeline"` in findings.json
2. Sentinel checks finding status before Tier 3 fixes — skips `"pipeline"` findings
3. When issue resolves, mark finding as `"fixed"`

The `_processed_findings` set persisted to disk alongside registry.json to survive restarts.

## Key Decision: Consumer Project Scope

The fix agent runs in the consumer project (not set-core). The investigation creates openspec artifacts in the consumer's `openspec/changes/` and the fix agent implements there. This is correct — the pipeline fixes runtime issues in consumer projects.
