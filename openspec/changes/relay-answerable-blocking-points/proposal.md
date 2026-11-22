## Why

The question relay answers only `AskUserQuestion`. A permission prompt, a confirmation a hook asks for, and a session that has finished its turn and waits for the next instruction either reach the channel as a one-way notification or do not reach it at all. In every one of those cases the owner, away from the terminal, can see that something is blocked but cannot unblock it. The user's rule (2026-11-22): *"minden hook és gate megszakítás is a wpc-kerdes-en keresztül tudjon átjönni és folytatódni"*, and for a finished session: *"vegye észre és jöjjön kiértesítés és folytathassam és/vagy adja be azt amit ajánlana a claude code is inputnak"*. Both mechanisms the fix needs were measured working on the runtime on 2026-11-22 (bug register B-188, B-190).

## What Changes

- **Permission carrier.** A `PermissionRequest` hook turns a permission prompt into a relay question with Allow / Deny options plus free text. Since the runtime routes a PreToolUse `ask` through the same dialog, this covers hook-raised confirmations as well. The hook hands the question to the existing two-way outbound. An answer resolves the dialog: allow, deny, or deny with the owner's free text as the message. The terminal dialog stays live the whole time, and whichever side answers first wins.
- **Continuation carrier.** A `Stop` hook with `asyncRewake` runs in the background after a turn the wait detector classified as DONE. It posts a continuation question carrying a short summary, one to three suggested next steps and free text. An answer wakes the idle session with the answer as its instruction. The suggestions come from set-core's own headless model call and are labelled as suggestions. Claude Code's own prompt suggestion is not available to hooks (measured).
- **Stale guards.**
  - When a permission prompt is answered in the terminal first, the carrier clears its waiting record. The bridge then closes the channel post through its existing release mechanism, so no bridge change is needed.
  - A prompt the owner types in the terminal supersedes an armed continuation. A late channel answer is then dropped with a log line and never injected.
- **No double report.** A permission prompt held by the permission carrier is not also posted as a one-way notification.
- **The wait detector** records its verdict per turn, with no text, so the continuation carrier acts only on DONE turns and never double-asks a WAITING one. Summary and suggestions come from a second headless call made only on DONE turns while the relay is on. That text lives only in the envelope handed to the outbound and is never written to disk by set-core.
- **Wiring.** `set-relay-wire` (machine-local, the notification hook's precedent) and the unwired-project check include the three new hook entries: PermissionRequest, async Stop and the UserPromptSubmit supersede marker. `set-deploy-hooks` is deliberately left out, so a consumer's tracked settings stay untouched (see design).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `agent-question-relay`: new requirements. A permission prompt is answerable from the channel. A finished turn is continuable from the channel. Stale answers never act. A held prompt is not double-reported. The wire check counts the new hooks.
- `agent-wait-detection`: the detector records its verdict for the turn (no text), and keeps its WAITING behaviour unchanged.

## Impact

- New carriers: `bin/set-hook-permission-relay`, `bin/set-hook-continue-relay`, `bin/set-hook-relay-supersede`, each a thin executable. The logic lives in `lib/set_orch/fleet/question_relay.py`, plus a new `lib/set_orch/fleet/continuation.py`.
- Changed: `lib/set_orch/fleet/wait_detect.py` (verdict record and suggestions), `question_relay.notify()` (skips a prompt the permission carrier holds), `_hooks_in` / `unwired_projects` / `wire_project`, `install.sh` (script list), this repository's `.claude/settings.json`, and the fleet relay API (an additive `kind` field).
- The bridge (separate repository) needs no change. Both new question kinds use the existing envelope and answer files, and its existing release check closes a withdrawn post. This holds only if each carrier keeps its waiting record in the shape the bridge reads.
- Depends on runtime behaviour measured on Claude Code 2.1.330: `PermissionRequest` hooks run beside a drawn dialog and resolve it, and `asyncRewake` wakes an idle session on exit 2. A runtime that lacks either falls back to today: the terminal and the one-way notification.
