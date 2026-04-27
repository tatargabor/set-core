## Context

The issue pipeline is a closed loop: gate/watchdog/sentinel detects a problem → IssueRegistry registers an Issue → IssueManager.tick() spawns InvestigationRunner → agent runs `claude --max-turns 20 ... /opsx:ff` → diagnosis lands on disk → IssueManager polls for completion and transitions the issue per `PolicyEngine.post_diagnosis_policy()`. The pipeline's failure modes all share one property: when the agent cannot finish, there is no secondary control surface to rescue the issue.

Three specific failures:

1. `--max-turns 20` is a hardcoded constant in `investigator.py:81`. On a real incident it was exhausted after 21 turns when the investigator re-read a corrupted file across several turns without progress. The diagnosis returned partial, confidence fell below `min_confidence` (0.85 by default), and policy routed to neither FIXING nor AWAITING_APPROVAL.

2. `IssueManager.tick()` handles five transitions but has no case for "stuck in DIAGNOSED". If `_apply_post_diagnosis_policy()` returns nothing actionable, the issue stays DIAGNOSED with no timer, no audit follow-up, no operator alert.

3. The investigation prompt has no language about recognising source corruption. When a file has duplicate top-level imports or repeated code blocks (common after a bad merge or a half-applied auto-fix), the agent treats each read as an independent attempt.

A fourth, adjacent gap: `set-recovery`'s rollback preview enumerates what will be undone but does not flag active fix-iss pipelines that will be orphaned by the rollback. An operator doing partial rollback loses visibility into mid-flight fix-iss work.

All four live in the same call graph (manager + investigator + recovery's preview) and share the same state source (IssueRegistry + state.json). Fixing together avoids cross-change rebase work.

## Goals / Non-Goals

**Goals:**
- Investigation budget is configurable and defaults to a value large enough for typical multi-file diagnoses (empirically 30-40 turns).
- DIAGNOSED issues with no forward transition path are surfaced to the operator within `diagnosed_stall_hours`.
- The investigator's agent prompt recognises one common trap (source corruption via duplicate blocks) and exits with a useful diagnosis instead of looping.
- Operator-driven rollback emits a visible warning when active fix-iss work sits outside the rollback scope.

**Non-Goals:**
- Switching investigator models mid-session (e.g. escalate sonnet→opus on max_turns hit). Evaluated but deferred — orthogonal to the primary gap, and model escalation is a bigger change.
- Auto-retry of investigations that hit max_turns. The new config raises the ceiling; if 40 is still insufficient, that's an issue classification problem, not a budget problem.
- Changes to the `_apply_post_diagnosis_policy` routing logic. The watchdog is a backstop; the primary policy routing stays unchanged.
- Rewriting the investigation prompt beyond the new corruption-detection paragraph.
- A general "rollback impact analyzer" (e.g. "these tests will break"). The warning is scoped to active issues only.

## Decisions

### D1: `max_turns` default of 40

**Decision:** Default `IssuesPolicyConfig.investigation.max_turns = 40`. The Anthropic CLI's `--max-turns` value caps the agent's tool-use iterations.

**Rationale:** The incident's investigation hit 21 turns. Doubling the budget (20→40) has two effects: (a) headroom for multi-file diagnoses and (b) headroom for corrupt-file re-reads even before the prompt improvement lands. 40 is also below common CLI rate-limit thresholds at default rate limits for Sonnet (~50 turns per minute).

**Alternative considered:** default 60. Rejected — at the level of cost/latency a 60-turn session costs noticeably more than 40, and empirical evidence is 40 is enough.

### D2: DIAGNOSED stall threshold of 2 hours

**Decision:** Default `diagnosed_stall_hours = 2`. Implemented as a `_check_diagnosed_stalls()` step inside `tick()`.

For each DIAGNOSED issue whose `diagnosed_at` is older than the threshold:
1. If the watchdog already fired once for this issue (tracked via `issue.extras["stalled_notification_sent"] = True`), skip.
2. Otherwise: audit-log `diagnosis_stalled_notification_sent`, call `self.notifier.on_stalled_diagnosis(issue, elapsed_seconds)` if the notifier has that method (`getattr(notifier, 'on_stalled_diagnosis', None)`), and set `issue.extras["stalled_notification_sent"] = True` to prevent repeats.

**Alternative considered:** use `_check_timeout_reminders`'s 50%/80% style. Rejected — DIAGNOSED has no deadline (no `timeout_deadline` field populated when the issue landed below auto_fix threshold). The timer starts at `diagnosed_at`, which is always set.

**Why one-time:** operators do not want a recurring alert for the same stuck issue. The first notification is actionable; subsequent ones are noise.

### D3: Corrupt-file prompt hint — scope-limited, low cost

**Decision:** Append a short paragraph to `INVESTIGATION_PROMPT` right before the "Instructions" section:

```
## Source corruption recognition

If you read a source file and notice:
- duplicate top-level imports (same import appearing 2 or more times)
- repeated blocks of code (the same function body, JSX block, or switch case appearing back-to-back)
- merge conflict markers that were accepted verbatim (`<<<<<<<`, `=======`, `>>>>>>>` left in the file)

Do NOT keep re-reading the file hoping to make sense of it. Emit your diagnosis immediately:
- root cause: "source corruption (duplicate blocks from bad merge/auto-fix)"
- fix: recommend `git diff HEAD~1 -- <file>` and removing the duplicates before the parent change retries

This applies even if the corruption blocks you from completing a full multi-file diagnosis —
a partial diagnosis with a clear fix path beats burning turns on noise.
```

**Alternative considered:** a source-corruption pre-check in dispatch that fails fast on duplicate-block files. Rejected for this change — the dispatcher is hot path and the prompt hint is a cheaper first-pass. The dispatcher-level check is a possible follow-up if the prompt hint proves insufficient.

### D4: Low-confidence auto-fix escape hatch (opt-in)

**Decision:** Add `auto_fix_conditions.low_confidence_after_hours` (default None = disabled). When set, a DIAGNOSED issue that has been stuck for longer than this many hours AND has confidence ≥ 0.4 will be promoted to FIXING with a warning tag in the audit log.

Default is disabled because operators have not yet opted into accepting partial-confidence fixes. The config key exists so per-mode config (`modes.prod.issues.policy`) can opt in for specific environments.

**Alternative considered:** relax `min_confidence` globally. Rejected — that changes baseline behavior for fresh high-severity diagnoses too.

### D5: Recovery preview warning — data-driven, not prescriptive

**Decision:** In `recovery.render_preview`, after the existing sections, add a "Warnings" section IF any active issue (state in INVESTIGATING, DIAGNOSED, AWAITING_APPROVAL, FIXING) has an `affected_change` NOT in the rollback scope. The section lists: issue id, state, affected_change, and the fix-iss child name if any.

**Format:**
```
  ⚠ Active fix-iss pipelines outside rollback scope:
      - ISS-004  state=DIAGNOSED  affected=admin-dashboard  child=fix-iss-004-admin-dashboard
```

**Rationale:** the rollback still proceeds. The warning exists to surface collateral so the operator can manually mark the outside-scope issues as DISMISSED or CANCELLED before rolling back. We do not block rollback on this — operators know their intent.

## Risks / Trade-offs

- **[Risk] Higher `max_turns` default increases token cost per investigation.** → Mitigation: the config is per-mode overridable; cost-sensitive environments can lower it. 40 turns at ~5k tokens per turn ≈ 200k tokens per investigation, well under Sonnet's 200k context window and the default `token_budget=50000` will fire first for long sessions.

- **[Risk] DIAGNOSED watchdog fires false-positive alerts for issues waiting on a real manual decision.** → Mitigation: the watchdog is one-time per issue and purely advisory (notification + audit entry). It does not force a state transition by default. The one-shot behavior means the operator is alerted once per issue; subsequent sits are silent until the issue transitions.

- **[Risk] Corrupt-file prompt hint misleads the agent on large legitimate files with intentional repetition.** → Mitigation: the hint explicitly lists patterns that indicate corruption (duplicate imports, merge markers) — these are mechanically distinct from intentional code duplication. Worst case: the agent emits a "source corruption" diagnosis that the human overrules. Lower cost than a stalled investigation.

- **[Trade-off] Recovery preview's active-issue warning adds visual noise when no issues are active.** → The section only renders when there's at least one active outside-scope issue. Empty → no section. No noise in the common case.

## Migration Plan

1. No state schema changes. New config keys have defaults that preserve prior behavior.
2. `max_turns=40` default takes effect immediately; any in-flight investigation is unaffected (the CLI passes `--max-turns` at spawn time).
3. `diagnosed_stall_hours=2` watchdog activates on next `tick()`; existing DIAGNOSED issues that have been sitting for longer than 2 hours will fire their one-time notification on the first tick after deployment. Expected behavior — this is precisely what the fix is for.
4. Rollback: if the watchdog misfires (e.g. notification flood during initial deployment), set `diagnosed_stall_hours` to a very large number via config to effectively disable. The audit entries remain for post-mortem.
5. The `auto_fix_conditions.low_confidence_after_hours` escape hatch is disabled by default — no migration risk for existing projects.

## Open Questions

- Should `_check_diagnosed_stalls` also move the issue to AWAITING_APPROVAL after N hours so it appears in the approval queue? Current decision: **no**, the watchdog is advisory only. A future change can promote it to queue-adding behavior after operator feedback.
- Should the corrupt-file prompt hint be extended to detect more patterns (e.g. truncated files, binary-encoded text in source)? Current decision: **no**, defer until we see another loop class in the wild. Start with the observed pattern.
