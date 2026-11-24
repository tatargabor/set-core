#!/usr/bin/env bash
# watch-auto-clear — the EXECUTOR of the auto-clear capability (specs: auto-clear).
#
# Loop: enumerate the runtime's live session records (~/.claude/sessions/<pid>.json), keep the
# ones belonging to --dir, evaluate the clear-gate for each, and — only when every gate holds —
# type `/clear` into the tmux pane that hosts the session. It is self-limiting by construction:
# after a clear the fresh session has no handoff marker, so it stays unarmed until its own next
# handoff passes the content gate. The gate only evaluates; THIS script is the only thing that
# types, and it types only on an eligible verdict.
#
# Safety properties (kept even when armed):
#   - every gate verdict is logged, pass or fail — absence is announced, never silent; the
#     repeated "no" verdict is deduped to shape changes plus a 30-min heartbeat (measured
#     2026-11-23: one consumer log grew to 47 MB, one session's verdict 879× in 3000 lines);
#   - --dry-run evaluates and logs without ever sending keys;
#   - --started-after drops sessions started before a moment (e.g. before the clear-reload
#     hook was wired into settings). OFF by default since 2026-11-24: measured on Claude Code
#     2.1.331, a running session picks up a reload hook added to project settings mid-run and its
#     /clear reloads (started-after-self-exclusion task 1.1), so "started before the wiring"
#     no longer means "cannot reload", and the filter only excluded sessions that could. Opt in
#     with an explicit moment, or `--started-after wired` for the tree's recorded wiring time
#     (.reload-wired-at, written once by init --auto-clear), on an older runtime that snapshots
#     hooks at start. The first skip of a session is announced in .excluded-<session8> (reason +
#     the claude --resume way out) and logged once, never typed into;
#   - a session with no writer path is skipped with a logged reason: no tmux pane hosts it
#     AND no fleet agent (ownerd roster, matched by pid) holds it;
#   - PRESENCE GATE (autopilot task 0.2, measured 2026-09-13 10:03:50Z: the watcher's /clear
#     landed inside a half-written human line, and the continue prompt fused with the human's
#     words): before typing ANYTHING, the input line is read (presence.mjs) — only an empty line
#     or a ghost suggestion may be typed into; typed text or an unreadable line skips the pass;
#   - TURN GATE, ONE VERIFIED ESCAPE (turn-state.mjs; measured 2026-09-13 21:24:39Z + 21:26:17Z on
#     consumer-worktree: /clear typed into a seat mid-turn does not execute — it QUEUES; both fires'
#     /clears and continue prompts sat in the queue and the seat worked 25+ min past the limit,
#     while the freshness gate kept passing because one long generation writes nothing to the
#     transcript): a visible spinner line means the turn is running — the executor sends ONE
#     Escape (measured 2026-09-14 probe: it interrupts the turn; a queued message is not
#     submitted, it lands back in the input line), re-verifies spinner-gone + input-line-safe,
#     and only then types. Further Escapes are measured harmful: on an idle empty line one opens
#     a popover that swallows typed input, and with text in the line one CLEARS the text;
#   - FIRE LOCK: the 21:26:17Z fire was the SECOND for a clear still in flight — nothing recorded
#     the first. After typing, the watcher writes {sid, at} to .set/handoff/.firelock-<pid>; a
#     later pass for the SAME sessionId holds until the clear takes effect (the pid's sessionId
#     changes) or 10 minutes pass;
#   - the CONTINUE confirm counts a fragment only inside a USER STRING entry (the 21:25:16Z
#     "CONTINUE confirmed" was false: the old whole-file grep matched "auto-continue" in a
#     skill_listing attachment present from the session's birth; a queued message leaves no user
#     entry, so a user-string hit is the only submitted evidence);
#   - no Ctrl-U before the command: the 10:03:50Z fused prompt carried the Ctrl-U byte literally,
#     so it never cleared the line — the presence + turn gates are what guarantee the line now;
#   - PROVENANCE: every text typed is logged first to <tree>/.set/handoff/typed.jsonl (when the
#     autopilot ledger is installed), so capture hooks never record it as the human's words.
#
# Writers, in order (9.2, measured 2026-09-13: 65 overnight skips of ELIGIBLE sessions whose
# ownerd-held pty no tmux pane hosts):
#   1. tmux send-keys into the pane whose descendant the session pid is;
#   2. OwnerClient.write to the fleet agent whose roster pid matches. Read-only fallback if
#      neither exists: the skip is logged, never silent.
#
# Sessions are matched against EVERY worktree of --dir (9.1, measured: a worktree agent's cwd
# is the worktree, and its handoff dir lives there too — gating it against the main tree
# would read the wrong marker and the wrong handoff).
#
# Usage:
#   watch-auto-clear.sh --dir <projectRoot> [--interval SEC] [--threshold N] [--freshness SEC]
#     [--background-work-blocks true|false] [--started-after ISO] [--gate PATH] [--dry-run]
#     [--auto-continue PROMPT] [--continue-delay SEC] [--autopilot]
#     [--compact-on-background true|false] [--compact-threshold N] [--log-max-kb KB]
#
#   --started-after ISO|wired   drop sessions whose process started before this moment. Omitted:
#                 no filter (the default since 2026-11-24, see above). `wired` = the tree's wiring
#                 stamp (.set/handoff/.reload-wired-at — the session's own tree first, then --dir);
#                 no stamp anywhere = no filter for that session.
#
#   --background-work-blocks   default false since 2026-11-23: background tasks and subagents survive
#                 /clear on 2.1.330 (docs/investigations/2026-11-23-background-survival-rerun.md).
#                 `true` makes the gate refuse unless the armed handoff declares "none" (fail-closed).
#
#   --arm-nudge true|false   default true. An idle session with no FRESH handoff marker (none, or one
#                 its later work made stale) at ≥ nudge-ratio × threshold (--nudge-ratio, default 1.0 in
#                 the gate: the handoff runs right before the clear) gets `/handoff` typed, so the clear
#                 that follows carries all its work (2026-11-23: 80 of 141 watched sessions in one consumer
#                 tree never armed; the former 0.6 asked at 240k and the 400k clear lost the rest). Each ask
#                 is recorded BEFORE typing (.handoff-nudged-<session8>, then .2, .3); a session is asked
#                 again only after it answered, at most 3 times. Same presence gate; a working turn is
#                 waited out (no Escape for a nudge).
#
#   --idle-minutes M / --idle-floor N   the WARM-IDLE trigger (change warm-idle-rotation), defaults 48 and
#                 200000 in the gate, 0 disables. The runtime compacts an idle 200k+ session by itself at
#                 ~53.8 min after its last request, a race no size threshold can win. A session idle for M
#                 minutes at ≥ N tokens is asked for its handoff (the arm-nudge record, with the word
#                 warm-idle) and, once armed by its own last act, cleared. Never with an Escape: the turn
#                 must already be idle. Past 54 min it is left alone, and "warm-idle missed" is logged once.
#
#   --compact-on-background true   when ONLY running background work refuses the clear (the gate's
#                 action `compact`), type /compact instead: the session — and its background agents —
#                 survive; the session's marker is removed after it, so the next one needs a fresh
#                 handoff. Never presses Escape for a compact: a working turn is waited out.
#
#   --log-max-kb KB   size rotation, the safety net under the "no" dedupe: at watcher start and at
#                 the top of every pass, a log past KB kilobytes (default 5120) is renamed to
#                 auto-clear.log.1 — any old .1 replaced — and the fresh file's first line names
#                 the rotation and the size. Measured 2026-11-23: one consumer log had grown to
#                 47 MB / 236 385 lines.
#
#   --auto-continue default   use the package's own continue prompt (DEFAULT_CONTINUE below).
#
#   --autopilot   every automatic continuation first runs .claude/hooks/autopilot/drift-guard.mjs
#                 against the FRESH session; without --auto-continue the package's default
#                 continue prompt is used.
#
# Run it under tmux/systemd/nohup — it must outlive the sessions it watches. Runtime state:
#   <root>/.set/handoff/auto-clear.log     one line per verdict
set -u

ARM_NUDGE="true"; NUDGE_RATIO=""; IDLE_MINUTES=""; IDLE_FLOOR=""
WARM_MISSED=" "   # sessions whose missed warm window was logged (a string set: macOS bash 3.2 has no -A)
DIR=""; INTERVAL=60; THRESHOLD=""; FRESHNESS=""; BG="false"; AFTER=""; AFTER_GIVEN=0; STAMP_MODE=0; WIRED_MS=""; GATE=""; DRY=0; LOG_MAX_KB=""
CONTINUE_PROMPT=""; CONTINUE_DELAY=20; AUTOPILOT=0; COMPACT_BG="false"; COMPACT_THRESHOLD=""
COMPACT_CONTINUE="Continue after an automatic /compact (compact-on-background): your background agents are still running and will notify you. Re-read your own handoff file in full, then continue its CURRENT next step - a later UPDATE section supersedes earlier next steps, and a step marked done is never redone. Write a fresh handoff before the context fills again."
DEFAULT_CONTINUE="Autopilot continue after an automatic /clear (auto-continue): read the reloaded handoff file in full - it is THIS session's own thread. Continue with its CURRENT next step - a later UPDATE section supersedes the original next-steps list, and a step marked done is never redone. A project-level goal or plan file is context, not a work queue: never take over a step or lane another session owns. Stop and wait only at a decision that the thread's recorded human direction does not already answer - ask it on its own line starting with NEED INPUT: so the keep-going hook lets the stop through."
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2;;
    --interval) INTERVAL="$2"; shift 2;;
    --threshold) THRESHOLD="$2"; shift 2;;
    --freshness) FRESHNESS="$2"; shift 2;;
    --background-work-blocks) BG="$2"; shift 2;;
    --started-after) if [ "$2" = "wired" ]; then STAMP_MODE=1; else AFTER="$2"; AFTER_GIVEN=1; fi; shift 2;;
    --gate) GATE="$2"; shift 2;;
    --auto-continue) CONTINUE_PROMPT="$2"; shift 2;;
    --continue-delay) CONTINUE_DELAY="$2"; shift 2;;
    --autopilot) AUTOPILOT=1; shift;;
    --compact-on-background) COMPACT_BG="$2"; shift 2;;
    --compact-threshold) COMPACT_THRESHOLD="$2"; shift 2;;
    --arm-nudge) ARM_NUDGE="$2"; shift 2;;
    --nudge-ratio) NUDGE_RATIO="$2"; shift 2;;
    --idle-minutes) IDLE_MINUTES="$2"; shift 2;;
    --idle-floor) IDLE_FLOOR="$2"; shift 2;;
    --log-max-kb) LOG_MAX_KB="$2"; shift 2;;
    --dry-run) DRY=1; shift;;
    *) echo "unknown flag: $1" >&2; exit 2;;
  esac
done
[ -n "$DIR" ] || { echo "--dir is required" >&2; exit 2; }
DIR="$(cd "$DIR" && pwd)"
GATE="${GATE:-$DIR/.claude/hooks/clear-gate.mjs}"
[ -f "$GATE" ] || { echo "gate not found: $GATE" >&2; exit 2; }
PRESENCE="$(dirname "$GATE")/presence.mjs"
[ -f "$PRESENCE" ] || { echo "presence check not found: $PRESENCE — re-run init --auto-clear (typing without it is how the 10:03:50Z collision happened)" >&2; exit 2; }
TURN="$(dirname "$GATE")/turn-state.mjs"
[ -f "$TURN" ] || { echo "turn-state check not found: $TURN — re-run init --auto-clear (typing without it is how the 21:24:39Z queue happened)" >&2; exit 2; }
# Beside the gate: unchanged for the per-repo copy, and the package's own modules when the package runs
# the watcher (`set-claude-handoff watch`, no per-repo copy).
AP_DIR="$(dirname "$GATE")/autopilot"
LEDGER="$AP_DIR/ledger.mjs"
DRIFT="$AP_DIR/drift-guard.mjs"
# `--auto-continue default` selects the package's continue prompt without hand-writing one.
[ "$CONTINUE_PROMPT" = "default" ] && CONTINUE_PROMPT="$DEFAULT_CONTINUE"
if [ "$AUTOPILOT" = "1" ]; then
  [ -f "$DRIFT" ] || { echo "--autopilot: drift guard not found: $DRIFT — run init --autopilot" >&2; exit 2; }
  [ -n "$CONTINUE_PROMPT" ] || CONTINUE_PROMPT="$DEFAULT_CONTINUE"
fi

LOG="$DIR/.set/handoff/auto-clear.log"
mkdir -p "$(dirname "$LOG")"
# Parsed with node, not `date -d` (GNU-only): on macOS `date -d` fails, AFTER_MS came back EMPTY
# and the --started-after filter silently turned off — the one filter that keeps a session which
# cannot reload from being cleared. An unparseable value now refuses to start instead.
AFTER_MS=""
if [ -n "$AFTER" ]; then
  AFTER_MS=$(node -e 'const t = Date.parse(process.argv[1]); if (Number.isFinite(t)) process.stdout.write(String(t))' "$AFTER" 2>/dev/null)
  [ -n "$AFTER_MS" ] || { echo "--started-after: cannot parse '$AFTER' as a date" >&2; exit 2; }
fi

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }

# Per-watcher memory for the "no" dedupe below: one small file per watched session, under a
# per-watcher temp dir (a string set would need declare -A, which macOS bash 3.2 lacks).
NO_DEDUPE_DIR="${CLAUDE_CODE_TMPDIR:-${TMPDIR:-/tmp}}/set-handoff-no-dedupe-$$"
# A failed creation silently disabled the dedupe — absence is announced, never silent.
mkdir -p "$NO_DEDUPE_DIR" 2>/dev/null || { log "warn  no-dedupe: cannot create $NO_DEDUPE_DIR — verdict lines repeat per pass"; NO_DEDUPE_DIR=""; }
# The dir must not outlive the watcher: otherwise one dir per lifetime accumulates in the temp
# dir. The EXIT trap covers a normal end; INT TERM HUP clean up AND exit — a trap replaces the
# signal's default terminate, so the explicit exit is what still ends the watcher.
# A trapped signal is also DEFERRED while bash waits for a foreground child, so the loop's
# `sleep "$INTERVAL"` (60 s in production) would hold a TERM sent to the watcher alone until it
# ran out. The loop therefore sleeps in the background and `wait`s, which a trapped signal
# interrupts at once; the handler kills that sleep too, so nothing of the watcher outlives it.
SLEEP_PID=""
cleanup_no_dedupe() {
  [ -n "$SLEEP_PID" ] && kill "$SLEEP_PID" 2>/dev/null
  [ -n "$NO_DEDUPE_DIR" ] && rm -rf "$NO_DEDUPE_DIR" 2>/dev/null
  return 0
}
trap cleanup_no_dedupe EXIT
trap 'cleanup_no_dedupe; exit 0' INT TERM HUP

# The verdict's SHAPE: $failed with every run of digits replaced by N — so a moving token count
# or freshness age (the measured churn: "tokens:184211 < 400000 … (-1s old)") is not a change.
# The second expression folds N.N into N: the gate prints decimal ages ("idle 55.1 min ≥ 54"),
# and a ticking tenth of a minute is the same moving number, not a change. \{1,\}, not \+ — BSD sed.
verdict_shape() { printf '%s' "$1" | sed -e 's/[0-9][0-9]*/N/g' -e 's/\(N\)\(\.N\)\{1,\}/\1/g'; }

# The per-pass "no" line is written only when THIS session's shape changed, or NO_HEARTBEAT_S
# passed since its last written line (a heartbeat, so a tail still shows the session is watched).
# The memory is per watcher: two watchers on one tree each keep their own and each log their own
# line. The "no writer path" nudge/skip lines use the same rule under their own key. Every other
# line (FIRE, NUDGE, request, warm-idle, other skips) is never deduped. rc 0 = write it.
NO_HEARTBEAT_S=1800
no_log_due() { # $1 = sid, $2 = shape
  local f now last seen
  [ -n "$NO_DEDUPE_DIR" ] || return 0
  f="$NO_DEDUPE_DIR/$(printf '%s' "$1" | tr -cd 'a-zA-Z0-9')"
  [ -n "$f" ] || return 0
  now=$(date +%s)
  last=""; seen=""
  if [ -f "$f" ]; then
    read -r last seen < "$f" 2>/dev/null
    case "$last" in ''|*[!0-9]*) last="" ;; esac
    if [ -n "$last" ] && [ "$seen" = "$2" ] && [ $((now - last)) -lt "$NO_HEARTBEAT_S" ]; then
      return 1
    fi
  fi
  if printf '%s %s\n' "$now" "$2" > "$f" 2>/dev/null && [ -s "$f" ]; then return 0; fi
  # A failed memory write degrades to the old behavior (repeat per pass) — announced, not silent.
  log "warn  no-dedupe: cannot write $f — the verdict line repeats until this works"
  return 0
}

# Size rotation — the safety net under the dedupe above (same measurement: one consumer log
# reached 47 MB / 236 385 lines). At watcher start and at the top of every pass: past
# --log-max-kb, auto-clear.log becomes .1 (any old .1 replaced) and the fresh file's first line
# names the rotation and the size. `wc -c <` is the portable size check.
LOG_MAX_KB="${LOG_MAX_KB:-5120}"
case "$LOG_MAX_KB" in ''|*[!0-9]*) echo "--log-max-kb must be an integer (KB), got: $LOG_MAX_KB" >&2; exit 2;; esac
# 0 is a valid integer but rotates every pass — the log never grows past one pass's lines.
[ "$LOG_MAX_KB" -gt 0 ] || { echo "--log-max-kb must be a positive integer (KB), got: $LOG_MAX_KB" >&2; exit 2; }
log_rotate() {
  local bytes
  [ -f "$LOG" ] || return 0
  bytes=$(wc -c < "$LOG" 2>/dev/null) || return 0
  bytes=$((bytes))   # BSD wc pads with spaces; arithmetic strips them
  [ "$bytes" -gt $((LOG_MAX_KB * 1024)) ] || return 0
  if mv -f "$LOG" "$LOG.1" 2>/dev/null; then
    log "rotate  auto-clear.log reached ${bytes} bytes (> ${LOG_MAX_KB} KB) — the previous content is in auto-clear.log.1"
  else
    log "warn  rotate failed — auto-clear.log stays above ${LOG_MAX_KB} KB"
  fi
}
log_rotate

if ! command -v tmux >/dev/null; then
  if python3 -c "import set_orch.fleet.owner_client" >/dev/null 2>&1; then
    log "tmux not available — the writer path is the fleet owner only"
  else
    echo "tmux not available and the fleet owner client is not importable — no writer path" >&2
    exit 2
  fi
fi
[ -f "$LEDGER" ] || log "note  autopilot ledger not installed — typed text is not provenance-logged"

# Every worktree of DIR is a legitimate session cwd — and each tree gates from ITS OWN
# .set/handoff (9.1). The main tree is first; worktree enumeration failing (plain dir, no
# git) leaves the main tree alone, which is the pre-9.1 behavior.
WORKTREES="$DIR"
while IFS= read -r wt; do
  [ -n "$wt" ] && [ "$wt" != "$DIR" ] && WORKTREES="$WORKTREES
$wt"
done < <(git -C "$DIR" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')

tree_of() { printf '%s\n' "$WORKTREES" | grep -Fx "$1"; }

# The wiring stamp (change started-after-self-exclusion): ONE ISO-8601 UTC-with-Z line at
# <tree>/.set/handoff/.reload-wired-at, written once by init --auto-clear, as epoch ms; "" when
# absent. Parsed with node's Date.parse — `date -d` is GNU-only (the AFTER_MS lesson below).
wired_ms_of() { # $1 = tree
  [ -f "$1/.set/handoff/.reload-wired-at" ] || return 0
  node -e 'const {readFileSync} = require("node:fs"); const t = Date.parse(readFileSync(process.argv[1], "utf8").trim()); if (Number.isFinite(t)) process.stdout.write(String(t))' \
    "$1/.set/handoff/.reload-wired-at" 2>/dev/null
}
ms_to_iso() { # $1 = epoch ms → ISO-8601 Z, or a spoken fallback
  node -e 'const t = Number(process.argv[1]); process.stdout.write(Number.isFinite(t) && t > 0 ? new Date(t).toISOString().replace(/\.\d{3}Z$/, "Z") : "an unknown moment")' "${1:-}" 2>/dev/null
}

# `--started-after wired`: the moment is the wiring, not the arming. Without it, every watcher
# restart measured its own start and re-excluded sessions that already had the hook (measured
# 2026-11-23: one tree's only working session, skipped 2858 times, silent). A corrupt stamp
# refuses to start, like a corrupt --started-after — a silently OFF filter that was asked for is
# how a session that cannot reload gets cleared.
if [ "$STAMP_MODE" = "1" ]; then
  WIRED_MS=$(wired_ms_of "$DIR")
  if [ -z "$WIRED_MS" ] && [ -f "$DIR/.set/handoff/.reload-wired-at" ]; then
    echo "wiring stamp is not a parseable date: $DIR/.set/handoff/.reload-wired-at" >&2
    exit 2
  fi
  while IFS= read -r wt; do
    [ -n "$wt" ] && [ "$wt" != "$DIR" ] && [ -f "$wt/.set/handoff/.reload-wired-at" ] || continue
    if [ -z "$(wired_ms_of "$wt")" ]; then
      echo "wiring stamp is not a parseable date: $wt/.set/handoff/.reload-wired-at" >&2
      exit 2
    fi
  done <<< "$WORKTREES"
fi

# The start-filter skip is ANNOUNCED, not silent (measured 2026-11-23: the only trace of one
# tree's 2858 skips was a per-minute log line nobody reads). The FIRST skip of a session writes
# .excluded-<session8> — the resume command on line 1, the reason below — and logs once; later
# passes stay quiet (the file's NON-EMPTINESS is the guard, so a second watcher cannot double-write
# either, exactly like nudge_record's noclobber). Nothing is ever TYPED into an excluded
# session: its stale hooks are exactly why it is excluded (D1).
#
# A 0-BYTE record is the disk-full leftover (the same failure that left the 2026-09-25 firelock
# empty: `>` creates the file, the write dies with ENOSPC): the old existence guard honoured the
# empty file for ever — the session excluded with no resume command, no reason, and no way to
# repair. So a 0-byte record counts as ABSENT: the body is written to a tmp file in the same
# dir and mv'd into place only while the target still does not exist (the re-check narrows the
# two-watchers race; both would write equivalent content anyway), and the repair logs the
# written line once like a first write.
excluded_record() { # $1 = tree, $2 = sid, $3 = startedAt ms, $4 = effective filter ms → rc 0 always
  local s8 f tmp
  s8=$(printf '%s' "$2" | tr -cd 'a-zA-Z0-9' | cut -c1-8)
  f="$1/.set/handoff/.excluded-$s8"
  [ -s "$f" ] && return 0
  mkdir -p "$1/.set/handoff" 2>/dev/null
  tmp="$f.tmp.$$"
  if printf '%s claude --resume %s\nExcluded by the start filter: this process started %s, before --started-after %s — its hook snapshot predates the clear-reload wiring, so a /clear here would reload nothing. Exit and run the resume command on line 1 (same session id, new process, current hooks) to be watched again.\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$2" "$(ms_to_iso "$3")" "$(ms_to_iso "$4")" > "$tmp" 2>/dev/null \
      && [ -s "$tmp" ] \
      && { [ -s "$f" ] || mv -f "$tmp" "$f" 2>/dev/null; } \
      && [ -s "$f" ]; then
    rm -f "$tmp" 2>/dev/null
    log "skip  $2  started before --started-after — .excluded-$s8 written (resume + reason), logged once"
  else
    rm -f "$tmp" 2>/dev/null
    log "skip  $2  started before --started-after"
  fi
}

# The exclusion record's other half (the resume hole): `claude --resume` keeps the session id but
# starts a NEW process whose startedAt postdates the stamp, so a resumed session passes the filter
# while its stale .excluded-<session8> stays. keep-going's post early-returns on the exclusion
# branch, so the unremoved record would suppress every threshold warning for ever — the session
# that did the right thing gets less advice than before it resumed. Removing it logs once: the
# file is gone, so its absence is the once-guard.
included_cleanup() { # $1 = tree, $2 = sid, $3 = effective filter ms ("" = filter off) → rc 0 always
  local s8 f
  s8=$(printf '%s' "$2" | tr -cd 'a-zA-Z0-9' | cut -c1-8)
  f="$1/.set/handoff/.excluded-$s8"
  [ -e "$f" ] || return 0
  rm -f "$f" 2>/dev/null
  if [ -n "${3:-}" ]; then log "included  $2  started after the filter — .excluded-$s8 removed"
  else log "included  $2  no start filter — .excluded-$s8 removed"; fi
}

# Provenance: logged BEFORE typing (specs: intent-ledger). $1 tree, $2 kind, $3 text, $4 session, $5 pid
typed() {
  [ -f "$LEDGER" ] || return 0
  node "$LEDGER" typed --dir "$1/.set/handoff" --kind "$2" --text "$3" --session "$4" --pid "$5" 2>/dev/null \
    || log "warn  typed-log write failed ($2) — capture may record this text as human"
}

# Presence (task 0.2): empty|ghost may be typed into; typed|unknown may not.
safe_to_type() { case "$1" in empty|ghost) return 0;; *) return 1;; esac; }
presence_tmux() { # $1 = pane
  local s; s=$(tmux capture-pane -p -e -t "$1" 2>/dev/null | node "$PRESENCE" 2>/dev/null)
  printf '%s' "${s:-unknown}"
}
presence_owner() { # $1 = fleet label — raw tail bytes, last input-row paint
  local s
  s=$(python3 - "$1" <<'PY' 2>/dev/null | node "$PRESENCE" --stream 2>/dev/null
import sys
try:
    from set_orch.fleet.owner_client import OwnerClient
    sys.stdout.write(OwnerClient().tail(sys.argv[1], max_bytes=20000)["data"].decode("utf-8", "replace"))
except Exception:
    pass
PY
)
  printf '%s' "${s:-unknown}"
}

# Turn state (the 21:24:39Z queue): working|queued|idle|unknown — only an idle seat may be cleared.
turn_tmux() { # $1 = pane
  local s; s=$(tmux capture-pane -p -e -t "$1" 2>/dev/null | node "$TURN" 2>/dev/null)
  printf '%s' "${s:-unknown}"
}
turn_owner() { # $1 = fleet label — from ACTIVITY: drained_total growth over 2 s + prompt row (turn-state.mjs classifyActivity)
  local raw delta
  raw=$(python3 - "$1" <<'PY' 2>/dev/null
import sys, time
try:
    from set_orch.fleet.owner_client import OwnerClient
    c = OwnerClient()
    t0 = c.tail(sys.argv[1], max_bytes=1)["drained_total"]
    time.sleep(2)
    r = c.tail(sys.argv[1], max_bytes=20000)
    print(r["drained_total"] - t0)
    sys.stdout.write(r["data"].decode("utf-8", "replace"))
except Exception:
    pass
PY
)
  delta=$(printf '%s\n' "$raw" | head -1)
  printf '%s\n' "$raw" | tail -n +2 | node "$TURN" activity "$delta" 2>/dev/null || printf 'unknown'
}

# ONE Escape, then re-verify (measured 2026-09-14 probe: one Escape interrupts the running turn;
# a repeat on an idle line opens a popover that swallows typed input, and with text in the line
# it clears the text — so never repeat blindly).
esc_tmux() { tmux send-keys -t "$1" Escape; }
esc_owner() { # $1 = fleet label
  python3 - "$1" <<'PY' 2>/dev/null
import sys
try:
    from set_orch.fleet.owner_client import OwnerClient
    OwnerClient().write(sys.argv[1], b"\x1b")
except Exception:
    pass
PY
}
stop_turn() { # $1=turn_fn $2=presence_fn $3=esc_fn $4=target — rc 0 only if the turn is over AND the line is safe
  local state pres
  state=$("$1" "$4")
  case "$state" in
    working|queued) ;;
    idle) return 0;;
    *) return 1;;  # unknown — do not act on an unreadable seat
  esac
  "$3" "$4"
  sleep 2
  state=$("$1" "$4")
  pres=$("$2" "$4")
  safe_to_type "$pres" || return 1
  [ "$state" = "idle" ] || return 1
}

# Fire lock (the 21:26:17Z double fire): held ⇒ a /clear for THIS sessionId is still in flight.
fire_lock_held() { # $1 = tree, $2 = pid, $3 = sid
  local f="$1/.set/handoff/.firelock-$2" state
  state=$(node "$TURN" lock "$f" "$3" 2>/dev/null)
  if [ "$state" = "held" ]; then return 0; fi
  rm -f "$f" 2>/dev/null || true
  return 1
}
# MEASURED 2026-09-25 20:06: the root disk was at 100 % — the firelock landed as a 0-byte file
# (`>` truncates, the write then fails with ENOSPC, `|| true` swallowed it), and the fresh
# session got NO handoff injected at all: the hook output never reached it. So the lock is
# written atomically and checked, and a failed write aborts the fire (returns 1).
fire_lock_write() { # $1 = tree, $2 = pid, $3 = sid
  local f="$1/.set/handoff/.firelock-$2"
  mkdir -p "$1/.set/handoff" 2>/dev/null
  if printf '{"sid":"%s","at":%s}\n' "$3" "$(( $(date +%s) * 1000 ))" > "$f.tmp" 2>/dev/null \
     && [ -s "$f.tmp" ] && mv -f "$f.tmp" "$f" 2>/dev/null; then
    return 0
  fi
  rm -f "$f.tmp" 2>/dev/null
  log "FIRELOCK FAILED  $3  could not write $f (disk full?) — not firing"
  return 1
}

# Clear request (clear-gate's verdict `.request`): a session that finished a unit of work asks to
# be cleared at that boundary, below the threshold. The watcher CLAIMS the file by rename before it
# types, so a `.clear-request-any` fires exactly once, and deletes the claimed copy after the clear.
# A request the gate refused as unparsable, next-less or stale is logged and removed — never acted
# on; one refused for its handoff stays (the session may still write the handoff that names next).
request_claim() { # $1 = tree, $2 = verdict, $3 = sid → echoes the claimed path; returns 1 when lost
  local f; f=$(printf '%s' "$2" | jq -r 'if .request.valid == true then .request.file else empty end' 2>/dev/null)
  [ -n "$f" ] || return 0
  local src="$1/.set/handoff/$f" dst
  dst="$src.taken-$(printf '%s' "$3" | tr -cd 'a-zA-Z0-9' | cut -c1-8)"
  if mv "$src" "$dst" 2>/dev/null; then
    log "request  $3  claimed $f next=$(printf '%s' "$2" | jq -r '.request.next') from=$(printf '%s' "$2" | jq -r '.request.from')"
    printf '%s' "$dst"; return 0
  fi
  log "skip  $3  request $f was taken by another fire — re-evaluating next pass"
  return 1
}
request_refused_cleanup() { # $1 = tree, $2 = verdict, $3 = sid
  local f r; f=$(printf '%s' "$2" | jq -r 'if .request.valid == false then .request.file else empty end' 2>/dev/null)
  [ -n "$f" ] || return 0
  r=$(printf '%s' "$2" | jq -r '.request.reason')
  case "$r" in
    unparsable|"no 'next'"|stale*) rm -f "$1/.set/handoff/$f" 2>/dev/null; log "request  $3  refused $f: $r — removed" ;;
    *) log "request  $3  refused $f: $r — kept" ;;
  esac
}

# Free-space gate (same measurement): a /clear under a near-full disk throws the context away
# while the reload cannot be delivered — the SessionStart hook output and the harness's own
# task files both need room. Both the tree's filesystem and the temp dir must have MIN_FREE_MB.
MIN_FREE_MB="${AUTO_CLEAR_MIN_FREE_MB:-2048}"
disk_ok() { # $1 = tree; prints the short reason on failure
  local d avail
  for d in "$1" "${CLAUDE_CODE_TMPDIR:-${TMPDIR:-/tmp}}"; do
    avail=$(df -Pk "$d" 2>/dev/null | awk 'NR==2 {print int($4/1024)}')
    if [ -z "$avail" ] || [ "$avail" -lt "$MIN_FREE_MB" ]; then
      printf '%s has %s MB free (< %s)' "$d" "${avail:-?}" "$MIN_FREE_MB"
      return 1
    fi
  done
}

# The continue prompt NAMES the thread's handoff: if the SessionStart injection is lost, the
# successor still knows which file is its own (2026-09-25: it had to grep the log to find it).
continue_text() { # $1 = tree, $2 = cleared sid
  local s8 m nev
  s8=$(printf '%s' "$2" | tr -cd 'a-zA-Z0-9' | cut -c1-8)
  m="$1/.set/handoff/.written-$s8"
  nev=$(awk '{print $2; exit}' "$m" 2>/dev/null)
  if [ -n "$nev" ] && [ -f "$1/.set/handoff/$nev" ]; then
    printf '%s (Handoff file of the cleared session %s: %s)' "$CONTINUE_PROMPT" "$s8" "$1/.set/handoff/$nev"
  else
    printf '%s (No .written-%s marker names a handoff for the cleared session — find its thread in .set/handoff/auto-clear.log before acting.)' "$CONTINUE_PROMPT" "$s8"
  fi
}

# The fleet-owner writer (9.2): roster lookup by pid.
fleet_label_for_pid() {
  [ -n "${1:-}" ] || return 0
  python3 - "$1" <<'PY' 2>/dev/null
import sys
try:
    from set_orch.fleet.owner_client import OwnerClient
    pid = int(sys.argv[1])
    for a in OwnerClient().list_agents():
        if a.get("pid") == pid:
            print(a.get("label", ""))
            break
except Exception:
    pass
PY
}

fleet_write() { # $1 = label, $2 = text (no Enter)
  python3 - "$1" "$2" <<'PY' 2>/dev/null
import sys
try:
    from set_orch.fleet.owner_client import OwnerClient
    sys.exit(0 if OwnerClient().write(sys.argv[1], sys.argv[2].encode("utf-8")) else 1)
except Exception:
    sys.exit(1)
PY
}

fleet_owner_enter() {
  python3 - "$1" <<'PY' 2>/dev/null
import sys
try:
    from set_orch.fleet.owner_client import OwnerClient
    OwnerClient().write(sys.argv[1], b"\r")
except Exception:
    pass
PY
}

# Step 5 of the cycle (--auto-continue, user ask 2026-09-13: "why we do the clear and reload
# is to continue work"): after a successful automatic clear, give the fresh session its first
# prompt — continue from the reloaded handoff. Fires ONLY after the watcher's own clears, never
# after a manual /clear (a human at the keyboard decides that themselves).
#
# MEASURED (2026-09-13, the second bugfix fire): text+Enter in ONE write raced the fresh
# session's SessionStart hook chain (timeouts up to 40s) — the TUI was not reading the pty yet,
# the Enter was swallowed, and the prompt sat in the input box until the user pressed it by
# hand. So: text first, Enter separately, then VERIFY from the pid's own fresh transcript
# (the runtime record rewrites sessionId on a clear) and re-press Enter up to 3× if needed.
verify_submitted() { # $1 = pid, $2 = fragment expected in a USER entry of the fresh transcript
  local sid slug
  sid=$(jq -r '.sessionId // empty' "$HOME/.claude/sessions/$1.json" 2>/dev/null)
  [ -n "$sid" ] || return 1
  slug=$(jq -r '.cwd // empty' "$HOME/.claude/sessions/$1.json" 2>/dev/null | sed 's/\//-/g')
  [ -n "$slug" ] || return 1
  local t="$HOME/.claude/projects/$slug/$sid.jsonl"
  # A whole-file grep confirmed nothing (the 21:25:16Z false confirm matched "auto-continue" in a
  # skill_listing attachment present from birth): only a user STRING entry counts (probe M2 — a
  # queued message leaves no user entry, so a user-string hit is real submission evidence).
  [ -f "$t" ] && node "$TURN" submitted "$t" "$2" 2>/dev/null
}

continue_finish() { # $1 = pid, $2 = where (log label), $3.. = how to press Enter again
  local pid="$1" where="$2" try
  shift 2
  # The fragment comes from the prompt ACTUALLY typed. The fixed "auto-continue" default could
  # never match a custom --auto-continue prompt (measured 2026-09-21 on a consumer seat: a
  # prompt with no such word, a whole-file grep that matched the reinjected handoff instead,
  # a false "confirmed", no Enter retry — the prompt sat unsent until a human pressed Enter).
  # Cut before any quote or backslash: the transcript line is JSON and escapes those.
  local fragment="${CONTINUE_FRAGMENT:-${CONTINUE_PROMPT:0:40}}"
  fragment="${fragment%%[\"\\]*}"
  [ -n "$fragment" ] || fragment="auto-continue"
  for try in 1 2 3; do
    sleep 5
    if verify_submitted "$pid" "$fragment"; then
      log "CONTINUE confirmed  prompt submitted (try $try) → $where"
      return 0
    fi
    [ "$try" -le 2 ] && "$@"
  done
  log "CONTINUE UNCONFIRMED  prompt not found in the fresh transcript after 3 tries → $where"
}

# The continuation gate: the FRESH session id (the runtime record rewrites it on a clear) and,
# under --autopilot, the drift guard's verdict for it (specs: drift-guard). Prints the fresh id.
continue_gate() { # $1 = pid, $2 = the cleared session id, $3 = tree
  local fresh verdict
  fresh=$(jq -r '.sessionId // empty' "$HOME/.claude/sessions/$1.json" 2>/dev/null)
  if [ -z "$fresh" ] || [ "$fresh" = "$2" ]; then
    log "CONTINUE held  no fresh session id on pid $1 after the clear of $2"
    return 1
  fi
  if [ "$AUTOPILOT" = "1" ]; then
    verdict=$(node "$DRIFT" --session "$fresh" --cwd "$3" --json 2>/dev/null)
    if [ "$(printf '%s' "$verdict" | jq -r '.continue // false' 2>/dev/null)" != "true" ]; then
      log "CONTINUE held  drift guard: $(printf '%s' "$verdict" | jq -r '[.checks[]? | select(.ok == false) | .name + ": " + .detail] | join("; ")' 2>/dev/null)  (fresh $fresh)"
      return 1
    fi
    log "CONTINUE drift guard passed  (fresh $fresh)"
  fi
  printf '%s' "$fresh"
}

continue_tmux() { # $1 = pane, $2 = pid, $3 = cleared sid, $4 = tree
  [ -n "$CONTINUE_PROMPT" ] || return 0
  sleep "$CONTINUE_DELAY"
  local fresh state
  fresh=$(continue_gate "$2" "$3" "$4") || return 0
  state=$(presence_tmux "$1")
  safe_to_type "$state" || { log "CONTINUE held  presence=$state in pane $1 — a human is at the keyboard"; return 0; }
  local text; text=$(continue_text "$4" "$3")
  typed "$4" continue "$text" "$fresh" "$2"
  tmux send-keys -t "$1" -l "$text"
  sleep 1.5
  tmux send-keys -t "$1" Enter
  log "CONTINUE sent  auto-continue prompt → pane $1"
  continue_finish "$2" "pane $1" tmux send-keys -t "$1" Enter
}
continue_owner() { # $1 = fleet label, $2 = pid, $3 = cleared sid, $4 = tree
  [ -n "$CONTINUE_PROMPT" ] || return 0
  sleep "$CONTINUE_DELAY"
  local fresh state
  fresh=$(continue_gate "$2" "$3" "$4") || return 0
  state=$(presence_owner "$1")
  safe_to_type "$state" || { log "CONTINUE held  presence=$state on fleet agent $1 — a human is at the keyboard"; return 0; }
  local text; text=$(continue_text "$4" "$3")
  typed "$4" continue "$text" "$fresh" "$2"
  fleet_write "$1" "$text" || { log "CONTINUE FAILED  owner-write of the prompt to $1"; return 0; }
  sleep 1.5
  fleet_owner_enter "$1"
  log "CONTINUE sent  auto-continue prompt → fleet agent $1"
  continue_finish "$2" "fleet agent $1" fleet_owner_enter "$1"
}

# After a /compact the session id stays, so the clear path's fresh-session gate does not apply: wait
# (no Escape) until the seat reads idle again, then type the compact-continue prompt naming the handoff.
compact_continue() { # $1 = kind tmux|owner, $2 = target, $3 = handoff path or empty
  [ -n "$CONTINUE_PROMPT" ] || return 0
  local i state pres text
  text="$COMPACT_CONTINUE${3:+ (Handoff: $3)}"
  for i in $(seq 1 36); do
    sleep 10
    if [ "$1" = tmux ]; then state=$(turn_tmux "$2"); pres=$(presence_tmux "$2"); else state=$(turn_owner "$2"); pres=$(presence_owner "$2"); fi
    [ "$state" = "idle" ] || continue
    safe_to_type "$pres" || { log "COMPACT-CONTINUE held  presence=$pres on $2 — a human is at the keyboard"; return 0; }
    if [ "$1" = tmux ]; then
      tmux send-keys -t "$2" -l "$text"; sleep 1.5; tmux send-keys -t "$2" Enter
    else
      fleet_write "$2" "$text" || { log "COMPACT-CONTINUE FAILED  owner-write to $2"; return 0; }
      sleep 1.5; fleet_owner_enter "$2"
    fi
    log "COMPACT-CONTINUE sent  → $2 after $((i * 10)) s"
    return 0
  done
  log "COMPACT-CONTINUE gave up  $2 never read idle within 360 s"
}
# The marker armed THIS compact; the next one needs a fresh handoff. Prints the handoff path first.
compact_disarm() { # $1 = tree, $2 = sid
  local s8 m nev
  s8=$(printf '%s' "$2" | tr -cd 'a-zA-Z0-9' | cut -c1-8); m="$1/.set/handoff/.written-$s8"
  nev=$(awk '{print $2; exit}' "$m" 2>/dev/null)
  rm -f "$m" 2>/dev/null && log "disarm  $2  removed .written-$s8 after /compact (next compact needs a fresh handoff)"
  [ -n "$nev" ] && printf '%s' "$1/.set/handoff/$nev"
}

# Is pid $1 a descendant of tmux pane pid $2? Walks the parent chain with `ps`, which Linux and
# macOS both have — /proc does not exist on macOS, so a /proc walk found no pane there at all.
# The tmux pane hosting pid $1 ("" when none).
pane_of_pid() {
  local pp loc
  while IFS=$'\t' read -r pp loc; do
    if is_descendant "$1" "$pp"; then printf '%s' "$loc"; return 0; fi
  done < <(tmux list-panes -a -F '#{pane_pid}\t#{session_name}:#{window_index}.#{pane_index}' 2>/dev/null)
}

# Arm nudge (--arm-nudge): the gate's `.nudge.due` names an idle, unarmed session at ≥ nudge-ratio ×
# threshold that was never nudged. The record is created with noclobber (O_EXCL) BEFORE typing, so two
# passes — or two watchers — can never type it twice; a write that fails types nothing.
NUDGE_TEXT="/handoff"
nudge_record() { # $1 = tree, $2 = sid, $3 = trigger (size|warm-idle), $4 = record name from the verdict → rc 0 only when THIS call created it
  local s8 f
  s8=$(printf '%s' "$2" | tr -cd 'a-zA-Z0-9' | cut -c1-8)
  case "$4" in .handoff-nudged-"$s8"|.handoff-nudged-"$s8".[0-9]) f="$1/.set/handoff/$4" ;;
    *) log "NUDGE FAILED  $2  the verdict named no valid record (${4:-none}) — not typing"; return 1 ;; esac
  [ -e "$f" ] && { log "nudge $2  already recorded in $(basename "$f") — never repeated"; return 1; }
  if ( set -C; printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$NUDGE_TEXT" "${3:-size}" > "$f" ) 2>/dev/null && [ -s "$f" ]; then
    return 0
  fi
  log "NUDGE FAILED  $2  could not create $f (taken, or disk full?) — not typing"
  return 1
}
nudge_session() { # $1 = tree, $2 = sid, $3 = pid, $4 = verdict
  local pane label pres turn tokens why rec nth
  tokens=$(printf '%s' "$4" | jq -r '.nudge.tokens // "?"' 2>/dev/null)
  why=$(printf '%s' "$4" | jq -r '.nudge.trigger // "size"' 2>/dev/null)
  rec=$(printf '%s' "$4" | jq -r '.nudge.record // empty' 2>/dev/null)
  nth=$(printf '%s' "$4" | jq -r '"\(.nudge.ask // 1)/\(.nudge.of // 1)"' 2>/dev/null)
  pane=$(pane_of_pid "$3")
  if [ -n "$pane" ]; then
    pres=$(presence_tmux "$pane"); turn=$(turn_tmux "$pane")
  else
    label="$(fleet_label_for_pid "$3")"
    if [ -z "$label" ]; then
      # Deduped like the "no" line (own key, same shape + heartbeat rule): measured 2026-11-24, an
      # unreachable 400k+ seat logged this every pass, 14 lines in 15 minutes, with nothing new.
      no_log_due "${2}nowriter" "$(verdict_shape "nudge $3")" \
        && log "nudge $2  due at $tokens but no tmux pane hosts pid ${3:-?} and no fleet agent holds it — no writer path (logged on change or every 30 min)"
      return 0
    fi
    pres=$(presence_owner "$label"); turn=$(turn_owner "$label")
  fi
  safe_to_type "$pres" || { log "nudge $2  due at $tokens but presence=$pres — a human may be typing; not this pass"; return 0; }
  [ "$turn" = "idle" ] || { log "nudge $2  due at $tokens but turn=$turn — waits (no Escape for a nudge)"; return 0; }
  if [ "$DRY" = "1" ]; then log "dry   $2  nudge due at $tokens — would type $NUDGE_TEXT once"; return 0; fi
  nudge_record "$1" "$2" "$why" "$rec" || return 0
  typed "$1" nudge "$NUDGE_TEXT" "$2" "$3"
  if [ -n "$pane" ]; then
    tmux send-keys -t "$pane" -l "$NUDGE_TEXT"; sleep 0.3; tmux send-keys -t "$pane" Enter
    log "NUDGE $2  $NUDGE_TEXT → pane $pane at $tokens tokens (trigger=$why, ask $nth; $(printf '%s' "$4" | jq -r '.nudge.reason' 2>/dev/null); recorded in $rec)"
  elif fleet_write "$label" "$NUDGE_TEXT"; then
    sleep 0.3; fleet_owner_enter "$label"
    log "NUDGE $2  $NUDGE_TEXT → fleet agent $label at $tokens tokens (trigger=$why, ask $nth; $(printf '%s' "$4" | jq -r '.nudge.reason' 2>/dev/null); recorded in $rec)"
  else
    log "NUDGE FAILED  $2  owner-write to $label — recorded anyway, never retried"
  fi
}

is_descendant() {
  local p="$1" want="$2"
  while [ -n "$p" ] && [ "$p" != "0" ] && [ "$p" != "1" ]; do
    [ "$p" = "$want" ] && return 0
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
  done
  return 1
}

if [ "$AFTER_GIVEN" = "1" ]; then AFTER_LABEL="$AFTER"
elif [ "$STAMP_MODE" = "1" ]; then AFTER_LABEL="wired${WIRED_MS:+ $(ms_to_iso "$WIRED_MS")}"
else AFTER_LABEL="any"; fi
log "watcher started dir=$DIR interval=${INTERVAL}s threshold=${THRESHOLD:-default} bg-blocks=$BG started-after=$AFTER_LABEL dry-run=$DRY auto-continue=$([ -n "$CONTINUE_PROMPT" ] && echo on || echo off) autopilot=$([ "$AUTOPILOT" = "1" ] && echo on || echo off) compact-on-background=$([ "$COMPACT_BG" = "true" ] && echo "on (≥ ${COMPACT_THRESHOLD:-default})" || echo off) arm-nudge=$([ "$ARM_NUDGE" = "true" ] && echo "on (ratio ${NUDGE_RATIO:-default})" || echo off) warm-idle=$([ "${IDLE_MINUTES:-48}" = "0" ] || [ "${IDLE_FLOOR:-200000}" = "0" ] && echo off || echo "on (${IDLE_MINUTES:-48} min, floor ${IDLE_FLOOR:-200000})")"
# Heartbeat, every pass, in every watched tree that has a handoff dir (the main tree always). keep-going
# reads it to know a watcher acts on its handoff demand when no per-repo watcher file exists. Only the
# mtime counts; the body names who wrote it.
heartbeat() {
  local t
  mkdir -p "$DIR/.set/handoff" 2>/dev/null
  while IFS= read -r t; do
    [ -d "$t/.set/handoff" ] && printf '%s %ss %s\n' "$$" "$INTERVAL" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$t/.set/handoff/.watcher-alive" 2>/dev/null
  done <<< "$WORKTREES"
  return 0
}

while :; do
  log_rotate
  heartbeat
  for rec in "$HOME"/.claude/sessions/*.json; do
    [ -f "$rec" ] || continue
    sid=$(jq -r '.sessionId // empty' "$rec" 2>/dev/null) || continue
    cwd=$(jq -r '.cwd // empty' "$rec" 2>/dev/null)
    tree=$(tree_of "$cwd")
    [ -n "$tree" ] || continue
    [ -n "$sid" ] || continue
    # The start filter, OFF unless asked: an explicit --started-after moment, or with `wired` the
    # session's own tree's wiring stamp (worktrees each have their own .set/handoff), falling back
    # to --dir's. No stamp anywhere = no filter for this session. With the filter off, a stale
    # .excluded record from an earlier filtered run is removed below (included_cleanup).
    EFF_AFTER=""
    if [ "$AFTER_GIVEN" = "1" ]; then
      EFF_AFTER="$AFTER_MS"
    elif [ "$STAMP_MODE" = "1" ]; then
      EFF_AFTER="$WIRED_MS"
      wired_here=$(wired_ms_of "$tree")
      [ -n "$wired_here" ] && EFF_AFTER="$wired_here"
    fi
    if [ -n "$EFF_AFTER" ]; then
      started=$(jq -r '.startedAt // 0' "$rec" 2>/dev/null)
      if [ "${started:-0}" -ge "$EFF_AFTER" ] 2>/dev/null; then :; else
        excluded_record "$tree" "$sid" "$started" "$EFF_AFTER"
        continue
      fi
    fi
    included_cleanup "$tree" "$sid" "$EFF_AFTER"
    slug=$(printf '%s' "$cwd" | sed 's/\//-/g')
    transcript="$HOME/.claude/projects/$slug/$sid.jsonl"
    gate_args=(--session "$sid" --transcript "$transcript" --dir "$tree/.set/handoff" --json --background-work-blocks "$BG")
    [ -n "$THRESHOLD" ] && gate_args+=(--threshold "$THRESHOLD")
    [ -n "$FRESHNESS" ] && gate_args+=(--freshness "$FRESHNESS")
    [ "$COMPACT_BG" = "true" ] && gate_args+=(--compact-on-background true)
    [ -n "$COMPACT_THRESHOLD" ] && gate_args+=(--compact-threshold "$COMPACT_THRESHOLD")
    if [ "$ARM_NUDGE" = "true" ]; then [ -n "$NUDGE_RATIO" ] && gate_args+=(--nudge-ratio "$NUDGE_RATIO")
    else gate_args+=(--nudge-ratio 0); fi
    [ -n "$IDLE_MINUTES" ] && gate_args+=(--idle-minutes "$IDLE_MINUTES")
    [ -n "$IDLE_FLOOR" ] && gate_args+=(--idle-floor "$IDLE_FLOOR")
    verdict=$(node "$GATE" "${gate_args[@]}" 2>/dev/null) || { log "skip  $sid  gate errored"; continue; }
    eligible=$(printf '%s' "$verdict" | jq -r '.eligible // false')
    failed=$(printf '%s' "$verdict" | jq -r '[.gates[] | select(.ok == false) | .name + ":" + .detail] | join("; ")')
    action=$(printf '%s' "$verdict" | jq -r '.action // empty')
    request_refused_cleanup "$tree" "$verdict" "$sid"
    trigger=$(printf '%s' "$verdict" | jq -r '.trigger // empty')
    if [ "$eligible" != "true" ] && [ "$action" != "compact" ]; then
      no_log_due "$sid" "$(verdict_shape "$failed")" && log "no    $sid  $failed"
      if [ "$(printf '%s' "$verdict" | jq -r '.idle.late // false')" = "true" ] && [ "${WARM_MISSED#* $sid }" = "$WARM_MISSED" ]; then
        WARM_MISSED="$WARM_MISSED$sid "
        log "warm-idle missed  $sid  $(printf '%s' "$verdict" | jq -r '.idle.reason')"
      fi
      if [ "$(printf '%s' "$verdict" | jq -r '.nudge.due // false')" = "true" ]; then
        nudge_session "$tree" "$sid" "$(jq -r '.pid // empty' "$rec" 2>/dev/null)" "$verdict"
      fi
      continue
    fi
    CMD="/clear"; [ "$action" = "compact" ] && CMD="/compact"
    [ "$action" = "compact" ] && log "compact  $sid  only background work refuses the clear ($failed) — /compact keeps the session and its agents"
    # Eligible — find the tmux pane hosting this session's process.
    pane=""; pane_pid=$(jq -r '.pid // empty' "$rec" 2>/dev/null)
    while IFS=$'\t' read -r pp loc; do
      if is_descendant "$pane_pid" "$pp"; then pane="$loc"; break; fi
    done < <(tmux list-panes -a -F '#{pane_pid}\t#{session_name}:#{window_index}.#{pane_index}' 2>/dev/null)
    if [ -z "$pane" ]; then
      label="$(fleet_label_for_pid "$pane_pid")"
      if [ -n "$label" ]; then
        state=$(presence_owner "$label")
        if ! safe_to_type "$state"; then
          log "skip  $sid  ELIGIBLE but presence=$state on fleet agent $label — a human may be typing; not typing this pass"
          continue
        fi
        if fire_lock_held "$tree" "$pane_pid" "$sid"; then
          log "skip  $sid  fire lock: a previous /clear is still in flight on pid $pane_pid — not re-firing"
          continue
        fi
        if [ "$CMD" = "/compact" ] && [ "$(turn_owner "$label")" != "idle" ]; then
          log "skip  $sid  compact waits: fleet agent $label is not idle (no Escape for a compact)"
          continue
        fi
        if [ "$trigger" = "warm-idle" ] && [ "$(turn_owner "$label")" != "idle" ]; then
          log "skip  $sid  warm-idle waits: fleet agent $label is not idle (no Escape for an idle rotation)"
          continue
        fi
        if ! stop_turn turn_owner presence_owner esc_owner "$label"; then
          log "skip  $sid  turn=$(turn_owner "$label") presence=$(presence_owner "$label") on fleet agent $label after one Escape — not typing this pass"
          continue
        fi
        if [ "$DRY" = "1" ]; then
          log "dry   $sid  ELIGIBLE (presence ok, turn stopped) — would owner-write $CMD to fleet agent $label"
          continue
        fi
        if ! why=$(disk_ok "$tree"); then
          log "skip  $sid  ELIGIBLE but disk low: $why — a reload could not be delivered; not clearing"
          continue
        fi
        claimed=""
        if [ "$CMD" = "/clear" ]; then claimed=$(request_claim "$tree" "$verdict" "$sid") || continue; fi
        fire_lock_write "$tree" "$pane_pid" "$sid" || { [ -n "$claimed" ] && mv "$claimed" "${claimed%.taken-*}" 2>/dev/null; continue; }
        log "FIRE  $sid  $CMD → fleet owner-write to $label (all gates held, presence ok, turn stopped${trigger:+, trigger=$trigger})"
        typed "$tree" "${CMD#/}" "$CMD" "$sid" "$pane_pid"
        if fleet_write "$label" "$CMD"; then
          sleep 0.3
          fleet_owner_enter "$label"
          log "sent  $sid  owner-write delivered to $label"
          [ -n "$claimed" ] && rm -f "$claimed" && log "request  $sid  executed — $(basename "$claimed") removed"
          if [ "$CMD" = "/compact" ]; then
            compact_continue owner "$label" "$(compact_disarm "$tree" "$sid")"
          else
            continue_owner "$label" "$pane_pid" "$sid" "$tree"
          fi
        else
          log "skip  $sid  owner-write FAILED for $label"
          [ -n "$claimed" ] && mv "$claimed" "${claimed%.taken-*}" 2>/dev/null && log "request  $sid  put back after the failed write"
        fi
        continue
      fi
      no_log_due "${sid}nowriter" "$(verdict_shape "skip $pane_pid")" \
        && log "skip  $sid  ELIGIBLE but no tmux pane hosts pid ${pane_pid:-?} and no fleet agent holds it — no writer path (logged on change or every 30 min)"
      continue
    fi
    state=$(presence_tmux "$pane")
    if ! safe_to_type "$state"; then
      log "skip  $sid  ELIGIBLE but presence=$state in pane $pane — a human may be typing; not typing this pass"
      continue
    fi
    if fire_lock_held "$tree" "$pane_pid" "$sid"; then
      log "skip  $sid  fire lock: a previous /clear is still in flight on pid $pane_pid — not re-firing"
      continue
    fi
    if [ "$CMD" = "/compact" ] && [ "$(turn_tmux "$pane")" != "idle" ]; then
      log "skip  $sid  compact waits: pane $pane is not idle (no Escape for a compact)"
      continue
    fi
    if [ "$trigger" = "warm-idle" ] && [ "$(turn_tmux "$pane")" != "idle" ]; then
      log "skip  $sid  warm-idle waits: pane $pane is not idle (no Escape for an idle rotation)"
      continue
    fi
    if ! stop_turn turn_tmux presence_tmux esc_tmux "$pane"; then
      log "skip  $sid  turn=$(turn_tmux "$pane") presence=$(presence_tmux "$pane") in pane $pane after one Escape — not typing this pass"
      continue
    fi
    if [ "$DRY" = "1" ]; then
      log "dry   $sid  ELIGIBLE (presence ok, turn stopped) — would $CMD pane $pane"
      continue
    fi
    if ! why=$(disk_ok "$tree"); then
      log "skip  $sid  ELIGIBLE but disk low: $why — a reload could not be delivered; not clearing"
      continue
    fi
    claimed=""
    if [ "$CMD" = "/clear" ]; then claimed=$(request_claim "$tree" "$verdict" "$sid") || continue; fi
    fire_lock_write "$tree" "$pane_pid" "$sid" || { [ -n "$claimed" ] && mv "$claimed" "${claimed%.taken-*}" 2>/dev/null; continue; }
    log "FIRE  $sid  $CMD → pane $pane (all gates held, presence ok, turn stopped${trigger:+, trigger=$trigger})"
    typed "$tree" "${CMD#/}" "$CMD" "$sid" "$pane_pid"
    tmux send-keys -t "$pane" -l "$CMD"
    sleep 0.3
    tmux send-keys -t "$pane" Enter
    [ -n "$claimed" ] && rm -f "$claimed" && log "request  $sid  executed — $(basename "$claimed") removed"
    if [ "$CMD" = "/compact" ]; then
      compact_continue tmux "$pane" "$(compact_disarm "$tree" "$sid")"
    else
      continue_tmux "$pane" "$pane_pid" "$sid" "$tree"
    fi
  done
  sleep "$INTERVAL" </dev/null >/dev/null 2>&1 & SLEEP_PID=$!
  wait "$SLEEP_PID"; SLEEP_PID=""
done
