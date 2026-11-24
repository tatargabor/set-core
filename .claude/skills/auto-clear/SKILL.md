---
name: auto-clear
description: >
  Arm, check, or switch off the automatic clear + handoff reload + auto-continue cycle in
  THIS project. `/auto-clear` arms it, `/auto-clear off` disables it (project or session
  scope), `/auto-clear status` reports what is measured, not what is assumed.
---

# auto-clear — arm, check, or switch off the automatic clear cycle

The cycle this arms, once running, needs no human keystrokes:

```
1. limit (default 400k)   the gate measures each session's OWN context number
   or warm-idle (48 min)   …or its idle time: ≥ 48 min with no request at ≥ 200k (before the runtime's idle compaction)
2. handoff készítés       the session writes a handoff; the write-check hook arms it
3. auto-clear             the executor types /clear when every gate holds
4. auto-reload            the SessionStart:clear hook injects the right handoff
5. auto-continue          the executor re-prompts the fresh session (optional, recommended)
```

Never clear without step 2: a session with no fresh handoff of its own is never cleared —
that is the one rule the machinery will not bend.

## Arguments

- *(none)* or `on` — full state check, then arm what is missing.
- `off [project|session <id8>]` — create a kill-switch file (below). Default: ask which scope.
- `status` — report measured state only; change nothing.

## 1. STATE first — measure, never assume

Run and report; each answer changes what you do next:

```bash
test -f .claude/hooks/clear-gate.mjs && echo gate-installed || echo gate-missing
grep -c "clear-gate\|handoff-reinject" .claude/settings.json   # hook wiring (0 = not wired)
command -v set-claude-handoff                                  # the package binary (plugin wiring)
ls -l .set/handoff/.watcher-alive 2>/dev/null                  # a watcher's heartbeat (≤ 10 min = live)
ls .set/handoff/.no-autoclear 2>/dev/null                      # PROJECT switch: present = OFF
pgrep -af "watch-auto-clear.sh" | grep "$(pwd -P)" || true     # is a watcher armed for THIS tree
```

A plugin may wire the hooks instead of `.claude/settings.json`: its `hooks.json` lines call
`set-claude-handoff hook …` (written by `set-claude-handoff plugin-files`). Then `gate-missing` and a 0
count are expected, and the binary plus the heartbeat are the evidence; say which wiring you found.

Also read `.claude/handoff.profile.md` — an `## Auto-clear` section there (threshold,
background-work policy, auto-continue prompt, persistence) is the project's tuning; without
it you use the defaults and SAY so.

## 2. ARM (argument `on`, or nothing when not armed)

1. Install package-owned files (safe on re-run — that IS the upgrade):
   `npx github:tatargabor/set-claude-handoff init --auto-clear`
   If the published package is older than your fixes, install from your local checkout instead.
2. **Two merges init never does** (consumer-owned; init prints them, you verify):
   - `.claude/settings.json`: SessionStart `clear|compact` matcher → `handoff-reinject-clear.mjs`,
     PostToolUse on handoff writes → the write-check arming hook (this project may already
     have its own — merge, never overwrite).
   - the statusline fragment (`templates/statusline-persist.sh`) — per-session token file.
   Verify each with a grep, and SAY which are wired and which are still manual.
   - PostToolUse `Write|Edit|MultiEdit|Bash` → `.claude/hooks/handoff-arm.mjs` — the ARMING hook,
     unless the project already has its own. Without one, no session is ever cleared (the gate
     logs `marker: no marker for this session` for ever).
   - **keep-going (optional, ask the user):** Stop → `keep-going.mjs stop --max 40` and PostToolUse
     `*` → `keep-going.mjs post` (exact JSON: `init` prints it). There is no `--threshold` here: keep-going
     reads the gate's default, so an upgrade moves both. A number in settings.json stays behind. The
     session then stops only on a line starting `NEED INPUT:` or `ALL DONE:`, and writes its own
     handoff at the limit. Off: `touch .set/handoff/.no-keepgoing` (or `.no-keepgoing-<session8>`).
     Its decisions are in `.set/handoff/keep-going.log`.
3. **Watcher**: if none is running for this tree, start one under tmux (or the fleet owner):
   ```bash
   tmux new-session -d -s auto-clear-watcher \
     "bash $PWD/.claude/hooks/watch-auto-clear.sh --dir $PWD \
      --interval 60 \
      --background-work-blocks <from profile, default false> \
      --auto-continue '<from profile, or: default>'"
   ```
   No `--started-after` here: the filter then defaults to the tree's recorded wiring time
   (`.set/handoff/.reload-wired-at` — ONE ISO-8601 UTC-with-Z line, never rewritten), so a
   watcher restart does not exclude sessions that already had the hook. `init --auto-clear`
   writes it only when a `.claude/settings*.json` already wires the reload hook, and its value
   is that file's mtime — at or after the real wiring edit, so it errs late (safe). Where no
   settings file wires it yet, init writes NOTHING and says so (`not yet …`): merge the hook
   first, then re-run `init --auto-clear` (or write the stamp by hand:
   `date -u +%Y-%m-%dT%H:%M:%SZ > .set/handoff/.reload-wired-at`). Pass `--started-after <iso>`
   explicitly only when no stamp exists — and then every session started before that moment is
   excluded, this arming session included.
   For reboot survival, install a `systemd --user` unit running the same
   command with `Restart=on-failure` and say you did.
4. **VERIFY** — an armed state without evidence is not armed:
   `tail -1 .set/handoff/auto-clear.log` must show `watcher started … auto-continue=…`;
   run the gate once by hand (`node .claude/hooks/clear-gate.mjs --session <any live id> …
   --json`) and show the 5-gate verdict. Report: threshold, which writer paths exist
   (tmux / fleet owner), auto-continue on/off, both switch states.
   Then say whether THIS session is covered: `test -f .set/handoff/.excluded-<session8>` (the id8
   from the statusline or the newest `~/.claude/sessions/<pid>.json`). Present ⇒ this session
   started before the filter: name it in this turn and give the resume command from the file's
   line 1 (`claude --resume <id>` — same session id, new process, current hooks), then let the
   user resume it. The resume path is not measured yet — task 1.1 of started-after-self-exclusion;
   verify the resumed session reloads after a `/clear` before relying on it. Do not expect a clear
   or a nudge to reach the excluded session: it is never typed into.

### macOS

Works on macOS since `d7f40c4` (no `/proc`, no GNU `date`). Needs `node`, `jq` and `tmux`, and
**Claude must run inside tmux** — on a Mac the tmux pane is the only way the watcher can type.
There is no systemd: keep the watcher in its own tmux session (as above), or use a launchd agent
for reboot survival. First run: add `--dry-run` and read the log — `dry … ELIGIBLE — would /clear
pane …` proves the session records and the pane lookup work on that machine.

## The handoff runs right before the clear

A clear carries only what the handoff holds. So the marker gate passes only for a FRESH handoff: the
session's last assistant record may trail its marker by at most `--request-window` (600 s). A handoff
written earlier and followed by more work is **stale**. Its clear is refused, on the size, request,
warm-idle and compact paths alike.

The watcher asks for the handoff **at the threshold** (`--nudge-ratio`, default 1.0). An idle session
with no fresh marker gets `/handoff` typed, and the clear follows at the next idle verdict. Each ask is
recorded before typing, as `.handoff-nudged-<session8>`, then `.2`, `.3`. A session is asked again only
after it answered the previous ask, and at most 3 times; after that it is left to the native compaction,
and the log says so.

Measured 2026-11-23: 80 of 141 watched sessions in one consumer tree never armed. The former 0.6 ratio
asked at 240k, and the 400k clear then lost everything done in between. Same presence gate as a clear;
a working turn is waited out. Off: `--arm-nudge false` (the size ask only; warm-idle has its own switch).

## Warm-idle rotation: the second trigger

The runtime compacts an IDLE session by itself. This is documented as *idle compaction* (setting
`idleCompaction`, floor `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS`, default 200 000). It starts ~53.8 min after
the last request, so no size threshold can come before it. Measured 2026-11-23: about 35 % of one product
family's auto compactions, and every one under 250k, were idle compactions.

So the watcher also acts on time. A session whose turn has ended, has had no request for
`--idle-minutes` (default 48), and holds at least `--idle-floor` tokens (default 200 000) is treated like
this:

- **Unarmed:** `/handoff` is typed once, through the same `.handoff-nudged-<session8>` record. Its
  trigger word `warm-idle` makes the handoff that answers it clear at once.
- **Armed by its own last act:** `/clear` is typed, with the same presence gate and fire lock as the
  size path, and FIRE names `trigger=warm-idle`. A marker older than the last work is NOT cleared for
  idle, because the work done since would be lost.
- **Never with an Escape:** a pane showing a running turn logs `warm-idle waits`.
- **Past 54 min:** nothing is typed, the size nudge included, and `warm-idle missed` is logged once.

Off: `--idle-minutes 0` (or `--idle-floor 0`). A tree that sets `CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS`
passes the same number as `--idle-floor`.

## Background agents: compact, not clear

Measured 2026-11-23 on 2.1.330: background bash tasks and background subagents SURVIVE a `/clear` and notify
the fresh session (`docs/investigations/2026-11-23-background-survival-rerun.md` in the package), so
`--background-work-blocks` defaults to false. The compact path below acts only when the block is switched
on (`--background-work-blocks true`): a `/compact` keeps the session, a `/clear` starts a new one. With
`--compact-on-background true` (and optionally `--compact-threshold N`, default 400 000) on the watcher, a session whose
ONLY refusal is running background work, with its own fresh handoff marker, idle and not opted out, gets `/compact`
instead; the marker is removed afterwards, so the next compact needs a fresh handoff. A working turn is waited out,
never interrupted with Escape for a compact.

## 3. OFF (argument `off`)

Kill switches are FILES, not promises — an agent's verbal "don't clear me" binds nothing:

- **project scope** (default for `off`): `mkdir -p .set/handoff && touch .set/handoff/.no-autoclear`
  — every session in this tree becomes ineligible, effective on the watcher's next pass (≤60s).
- **session scope**: `touch .set/handoff/.no-autoclear-<session8>` (`session8` = first 8
  alphanumeric chars of the session id, shown in the statusline). For YOUR OWN session, take
  the id from the statusline or the newest `~/.claude/sessions/<pid>.json`.

Re-enable by deleting the file. `status` always reports which switches exist.

## 4. What stays true however you arm it

- Nothing project-specific belongs in this skill: per-project tuning lives in
  `.claude/handoff.profile.md` (`## Auto-clear` section) — propose a section, never write it
  without the user's yes.
- A session the start filter excludes is told ONCE, in `.set/handoff/.excluded-<session8>`
  (the resume command + the reason), and the skip is logged once — never typed into. Its way
  out: `claude --resume <id>` restarts the same session id with current hooks, and it is
  watched again.
- The gate only ever EVALUATES; the executor types. Keep that split when you wire anything new.
- Every verdict is logged to `.set/handoff/auto-clear.log` — pass or fail. If a session is
  not being cleared, the reason is in the log, not in anyone's memory.
