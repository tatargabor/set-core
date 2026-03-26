## Replan Gate Decision Tree

```
_check_all_done() returns True
        │
        ▼
auto_replan = true?  ──no──►  done
        │yes
        ▼
failed_count > 0?  ──yes──►  replan (domain_failure trigger)
        │no
        ▼
coverage check:
  reconcile_coverage()
  all requirements "merged"?  ──yes──►  done (skip replan)
        │no
        ▼
uncovered requirements exist?  ──yes──►  replan (coverage_gap trigger, only uncovered domains)
        │no
        ▼
done (edge case — shouldn't happen)
```

The key insight: when `truly_complete == total && failed_count == 0`, we check coverage BEFORE entering replan. If coverage is 100%, there's nothing to replan.

## No-Op Detection

In `execute_merge_queue`, before running integration gates:

```
worktree has commits beyond base?
  │no → mark "merged" (no-op), skip gates, archive
  │yes → normal gate flow
```

Check: `git rev-list --count {merge_base}..HEAD` in the worktree. If 0 beyond the integration merge commit → no-op.

## Novelty Check Enhancement

Current check (line 1457): only filters `new_names ⊆ failed_names`.

Enhanced: also filter changes whose scope overlaps >80% with merged changes. This is hard to do precisely without LLM, so instead: pass merged change summaries to the replan prompt so the LLM knows what's already done and doesn't re-propose it.

This is already partially done via `replan_ctx.completed_names` — the issue is that the LLM in "batch_complete" mode ignores it. The fix is the gate itself: don't call the LLM at all when coverage is 100%.
