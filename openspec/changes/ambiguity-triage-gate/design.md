## Context

The digest pipeline detects spec ambiguities and stores them in `ambiguities.json`. Currently these are passed to the planner as informational context with the comment "decide or flag for human review" (planner.sh:671). There is no gate, no triage mechanism, and no tracking of what happened with each finding. The planner may silently ignore ambiguities or make inconsistent decisions across changes.

Current flow: `digest → ambiguities.json → planner gets raw JSON → no feedback`

The reporter renders ambiguities as a flat `<ul>` (reporter.sh:129-131) with no resolution info.

## Goals / Non-Goals

**Goals:**
- Allow human triage of ambiguities before planning (soft gate, not blocking)
- Track resolution of every ambiguity through the pipeline (who decided, what was decided)
- Generate an editable markdown template for comfortable triage
- Make the planner explicitly resolve `defer`-ed ambiguities with rationale

**Non-Goals:**
- Hard gate that blocks all pipelines (always allow `continue` without triage)
- Auto-resolution or AI-assisted triage (human decision point)
- Changing how the digest detects ambiguities (detection logic stays the same)
- Interactive CLI triage (markdown file is sufficient)

## Decisions

### D1: Triage file format — Markdown with parseable markers

Generate `triage.md` in `wt/orchestration/digest/` after each digest run. Each ambiguity gets a section with `**Decision:**` and `**Note:**` fields. The pipeline parses these with `grep`/`sed`.

**Why not JSON?** User needs to read descriptions, think, and write free-text notes. Markdown is natural for this. The parseable markers (`**Decision:** fix|defer|ignore`) keep it machine-readable.

**Why not extend ambiguities.json directly?** Users shouldn't hand-edit JSON — easy to break syntax. The triage.md is the human interface, ambiguities.json is the machine interface. Triage decisions get merged back into ambiguities.json by the pipeline.

### D2: Gate placement — between digest freshness check and planner prompt construction

In `cmd_plan()`, after the auto-digest trigger block (line 428-453) and before directive resolution (line 455+). This is the natural insertion point — digest is guaranteed fresh, and we haven't started building the planner prompt yet.

Gate behavior:
1. If `triage.md` doesn't exist → generate it, print summary, pause
2. If `triage.md` exists but has untriaged items (blank decisions) → print summary, pause
3. If all items triaged → proceed, merge decisions into ambiguities.json
4. If zero ambiguities → skip entirely (no triage.md generated)

"Pause" means: in interactive mode (`wt-orchestrate plan`), print message and exit 0 with a clear message. In automated mode (`wt-orchestrate start`), treat missing triage as "continue" (all items implicitly `defer`). This ensures the orchestrator never blocks waiting for human input.

### D3: Resolution fields in ambiguities.json

After triage is processed, each ambiguity entry gets two new fields:
```json
{
  "id": "AMB-003",
  "type": "underspecified",
  "description": "...",
  "resolution": "deferred",
  "resolution_note": "Planner will decide in cart-management change",
  "resolved_by": "triage"
}
```

`resolution` values: `fixed`, `deferred`, `ignored`, `planner-resolved`
`resolved_by` values: `triage` (human), `planner` (AI), `auto` (implicit defer in automated mode)

### D4: Planner prompt modification

For `defer`-ed ambiguities, change the planner prompt from the current generic "decide or flag for human review" to a structured instruction:

```
## Deferred Ambiguities (N items — you MUST resolve each)
For each deferred ambiguity below, include a resolution in your plan output:
- In the change that addresses the affected requirements, add a "resolved_ambiguities" field
- Specify what decision you made and why

[JSON of defer-only ambiguities]
```

`ignore`-ed ambiguities are excluded from the planner prompt entirely.
`fixed`-ed ambiguities are excluded (spec was corrected, re-digest removed them).

### D5: Planner output schema extension

Add optional `resolved_ambiguities` field to each change in plan output:
```json
{
  "name": "cart-management",
  "resolved_ambiguities": [
    {"id": "AMB-003", "resolution_note": "Will sum quantities on cart merge conflict"}
  ]
}
```

After plan generation, merge these back into ambiguities.json with `resolution: "planner-resolved"` and `resolved_by: "planner"`.

### D6: HTML report enhancement

Replace the flat `<ul>` with a table showing: ID, type, description, resolution, note, resolved_by. Color-code by resolution: green (fixed), blue (deferred/planner-resolved), gray (ignored), red (unresolved).

### D7: Triage preservation across re-digest

When re-digest runs and regenerates `ambiguities.json`, existing triage decisions in `triage.md` are preserved for ambiguities that still exist (matched by ID). New ambiguities get blank triage entries appended. Removed ambiguities get marked `[REMOVED]` in triage.md but are not deleted (audit trail).

## Risks / Trade-offs

**[Risk] triage.md parsing fragility** → Use strict regex for `**Decision:**` lines. Validate parsed values against allowed set. If parsing fails, treat as untriaged (safe default).

**[Risk] Automated pipeline blocks on missing triage** → D2 explicitly handles this: automated mode (`wt-orchestrate start`) auto-defers. Only interactive `plan` command pauses.

**[Risk] Planner ignores resolution instruction** → Validate plan output: if deferred ambiguities exist but no `resolved_ambiguities` in any change, log warning. Don't block — the pipeline is best-effort on AI compliance.

**[Trade-off] Extra step in workflow** → Triage is optional. Zero ambiguities = no triage file. In automated mode = auto-defer. Only blocks when there are findings AND user chose interactive mode.
