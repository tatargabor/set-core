# fleet-relay-teach — measurements

## M1 — the screens, on the running dashboard, 2026-11-24 ~12:20 (task 4.4)

Checked in Chrome on `localhost:7400/fleet` after `systemctl --user restart set-web` (12:19:30):
- Each waiting row has `details · teach · to terminal ↩`.
- **Details** on a real waiting question shows:
  - "waits for your answer on the channel";
  - the full question text;
  - the three options, with the recommended one visible;
  - `decider: no-decision — abstained: …` with the model's reason;
  - a `teach…` control.

  The overlay floats over the panel's rows, and nothing in the panel or under it moved.
- **Teach** shows the question, the options as one-click fills, the answer pre-filled with the
  recommended option, the explanation field with its example, and the line naming the target
  file, the commit and "not pushed". It was closed without saving, because that question belongs
  to another session.

## M2 — a save end to end on the live server, against a scratch git project (task 5.1, first half)

A waiting call and a decider record were placed in the live relay state for a scratch repository.
A stand-in process named `set-hook-…` held the record live, and another file was staged in the
repository. The call was taught from the panel with the explanation
"ha a tervezet módosítás le van ellenőrizve, mehet".
- Overlay: "Answered — the agent has it. Rule committed in teach-proj (main) as e285760 —
  .claude/rules/auto-answer-taught.md. Not pushed." It closed itself after 10 s.
- `git show --stat HEAD`: one file, `.claude/rules/auto-answer-taught.md`, +14. Message
  `auto-answer: taught rule 2026-11-24`. `git diff --cached --name-only` still listed the other
  file (AC-7, live).
- The entry was verbatim: question, answer, `When / why`, date. No session id or path.
- The relay's answer file held `{"valasz": "Igen, mehet (Recommended)"}`.
- set-web's journal: `rule appended … in teach-proj; answered=True commit=e285760`, with no
  rule text.
- The fake records were removed afterwards and the stand-in process stopped.

## M3 — the real decider applies the rule (task 5.1, second half; AC-9, AC-10)

`auto_answer.decide()` was run on the scratch project with no session, so the sources-only
fallback ran: one real model call. The question was "Mehet élesbe a teszt weboldal? A tervezet
módosítását ellenőriztem, a review zöld." Result:
- `Igen, mehet (Recommended)`, tier `decided`, confidence 0.93, `outward: false`;
- one reference to `auto-answer-taught.md`, checked: "**Answer:** Igen, mehet (Recommended)";
- `is_taught_reference` → True, so `exclusion(…, taught=True)` → None.

The same answer without the rule → `outward step: production`. A fork of a live session was not
run. The fork takes the same prompt, with the session's conversation in addition.

## M4 — what was learned while building it

- **The relay's waiting record carries no question text, deliberately.** Adding it broke three
  relay tests that assert exactly that, so the change was reverted. Details and Teach read the
  text only from the decider's private pending record. A call the decider never saw can be read
  in outline but not taught.
- **Mutation round (task 2.3):** 4 mutants, all caught:
  - drop `checked`;
  - drop the path match;
  - drop `decision`;
  - test `taught` before the permission guard (2 tests fail).
- **Web suite:** 9 failing at the end, 5 on a clean HEAD worktree. The extra failures are in
  `fleetSurface.test.tsx`. It flips between 0 and 2 failures on HEAD as well (3 runs each side),
  so it is flaky, not this change.
