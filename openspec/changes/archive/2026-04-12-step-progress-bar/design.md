# Design: step-progress-bar

## Step lifecycle

```
dispatch_change()     → current_step = "planning"
  FF creates artifacts → (no transition — still planning)
  /opsx:apply starts  → current_step = "implementing"

Agent done (loop_status=done):
  → current_step = "integrating"

_run_integration_gates():
  gates pass → current_step = "merging"
  gates fail → current_step = "fixing"  (retry dispatch)

_merge_change() success:
  → current_step = "archiving"

archive complete:
  → current_step = "done"
```

## Python: where to set current_step

| Location | Transition | current_step |
|----------|-----------|--------------|
| `dispatcher.py:dispatch_change()` | new dispatch | `planning` |
| `dispatcher.py:resume_change()` with retry_context | retry dispatch | `fixing` |
| `dispatcher.py:resume_change()` without retry | resume | `implementing` |
| `engine.py:_poll_active_changes()` agent done | agent finished | `integrating` |
| `merger.py:_run_integration_gates()` start | gates begin | `integrating` |
| `merger.py:_run_integration_gates()` e2e fail + redispatch | gate retry | `fixing` |
| `merger.py:execute_merge_queue()` gates pass, merge start | merge | `merging` |
| `merger.py:execute_merge_queue()` merge success | post-merge | `archiving` |
| `merger.py:execute_merge_queue()` archive done | terminal | `done` |

Each transition: `update_change_field(state_file, name, "current_step", step)` + event emit.

## Python: event

```python
event_bus.emit("STEP_TRANSITION", change=name, data={
    "from": old_step, "to": new_step
})
```

## Web: StepBar component

```tsx
// Steps displayed as letter badges, same as GateBar
const steps = [
  { key: 'planning',      label: 'P', title: 'Planning (artifact creation)' },
  { key: 'implementing',  label: 'I', title: 'Implementing (tasks)' },
  { key: 'fixing',        label: 'F', title: 'Fixing (gate retry)' },
  { key: 'merging',       label: 'M', title: 'Merging (integration + ff-only)' },
  { key: 'archiving',     label: 'A', title: 'Archiving (spec sync)' },
]

// Color logic:
// - Steps before current_step → green (completed)
// - current_step → blue + animate-pulse
// - Steps after → gray (pending)
// - 'fixing' when active → amber (retry)
```

## Web: layout in ChangeTable

```
| Change name | Steps      | Gates     | Status  | Tokens |
|-------------|------------|-----------|---------|--------|
| foundation  | P I _ M A  | B T _ E _ | merged  | 24K    |
| auth        | P I _ _ _  | _ _ _ _ _ | running | 7K     |
```

Steps and Gates side by side. Steps show lifecycle progress, Gates show quality results.
