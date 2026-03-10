## Why

The digest detects spec ambiguities (underspecified, contradictory, missing references) but the pipeline treats them as informational noise — they're passed to the planner with a "decide or flag" comment but there's no gate, no triage mechanism, and no way to track what happened with each finding. With 16+ ambiguities in a real spec, some need spec fixes before planning while others are fine for the planner to resolve. Without a decision point, either the planner silently guesses at ambiguous specs, or the user must manually inspect `ambiguities.json` and hope the planner did the right thing.

## What Changes

- **Triage template generation**: After digest, generate a human-editable `triage.md` in the digest directory with each ambiguity pre-formatted for decision (`fix` / `defer` / `ignore`) and a note field
- **Soft gate in pipeline**: Between digest and plan, the pipeline checks for untriaged ambiguities. If `triage.md` doesn't exist or has unresolved items, it pauses with a summary and options (continue / review / abort). If all items are triaged, it proceeds automatically.
- **Planner resolution tracking**: Ambiguities marked `defer` are passed to the planner with an instruction to fill a `resolution_note` explaining the decision. The planner output includes resolved ambiguities alongside the plan.
- **Resolution in ambiguities.json**: Add `resolution` (`fixed` / `deferred` / `ignored` / `planner-resolved`) and `resolution_note` fields to each ambiguity entry, populated from triage + planner output
- **HTML report integration**: The orchestration HTML report shows final resolution state per ambiguity (who decided, what was decided)

## Capabilities

### New Capabilities
- `ambiguity-triage`: Triage template generation, soft gate between digest and plan, resolution tracking through pipeline to HTML report

### Modified Capabilities
- `spec-digest`: Add `resolution` and `resolution_note` fields to ambiguity entries in `ambiguities.json`, generate `triage.md` after digest
- `orchestration-html-report`: Display ambiguity resolution state (decision + note + who decided) in the report

## Impact

- `lib/orchestration/digest.sh`: triage.md generation after digest output, resolution field writing
- `lib/orchestration/planner.sh`: gate check before planning, pass defer items with resolution instruction, capture planner resolution notes
- `lib/orchestration/report.sh` (or equivalent): render ambiguity resolution in HTML
- `wt/orchestration/digest/triage.md`: new file (generated, user-edited)
- `wt/orchestration/digest/ambiguities.json`: schema extension (resolution fields)
- `tests/orchestrator/test-digest-integration.sh`: new test cases for triage + gate + resolution
