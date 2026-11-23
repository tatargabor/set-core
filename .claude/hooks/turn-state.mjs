#!/usr/bin/env node
/**
 * turn-state — is this session's turn RUNNING, and is a message queue pending? (autopilot task group 0)
 *
 * WHY: at 21:24:39Z and 21:26:17Z (2026-09-13, consumer-worktree) the watcher typed /clear into a
 * seat that was mid-turn in one long generation. Text typed while a turn runs does not execute — it
 * QUEUES — so both /clears and both continue prompts sat in the input queue, and the seat worked 25+
 * minutes past the limit. The freshness gate had read the seat as idle because a single long
 * generation writes nothing to the transcript, and the input-line presence gate cannot see this
 * case: the input line is EMPTY while a turn runs.
 *
 * THE RULE (measured live on Claude Code 2.1.270, throwaway tmux pane, 2026-09-14):
 *   working  a spinner status line is on the visible screen: "✻ Wibbling… " / "* Dilly-dallying… " —
 *            one animation glyph (or '*'), one space, a Capitalized gerund, U+2026. The glyph rotates;
 *            the shape does not.
 *   queued   while messages sit in the queue, the input row reads "Press up to edit queued messages"
 *            (the presence gate already reads that row as "typed" — this is the second line of defense).
 *   idle     no spinner, no queue hint; the input row is empty or a ghost suggestion.
 *   ESCAPE, measured on this build: ONE Escape interrupts the running turn ("⎿ Interrupted · What
 *     should Claude do instead?"); a queued message is NOT submitted — it lands back in the input
 *     line, editable. A further Escape with text in the line CLEARS the text, and an Escape on an
 *     empty idle line opens a small popover (a "● high · /effort" line) that swallows typed input.
 *     ⇒ the executor sends AT MOST ONE Escape, verifies the effect, and never repeats blindly.
 *   tmux: `capture-pane -p -e`. Fleet owner path: ownerd offers raw output bytes (`tail`); the same
 *   patterns are matched against the tail's last window (--stream). NOT measured on that path:
 *   whether a spinner repaint always lands inside the last window of a long, busy tail.
 *   No decision possible ⇒ `unknown`, and the executor treats unknown as "do not type".
 *
 * Also hostable here (used by watch-auto-clear.sh, testable without a terminal):
 *   transcriptSaysSubmitted — "the continue prompt was submitted" must mean a USER STRING entry
 *     contains it. The 21:25:16Z confirm was a false positive: the old check grepped the whole
 *     transcript for "auto-continue", and every transcript contains that string from birth
 *     (skill_listing attachment, reinjected handoff preview). A queued message leaves NO user entry
 *     (probe M2), so a user-string hit is the only submitted evidence.
 *   fireLockState — the 21:26:17Z second fire happened because nothing recorded that a /clear was
 *     already in flight. The lock holds re-fires until the clear takes effect (the pid's sessionId
 *     changes) or the max wait passes.
 *
 * Usage:
 *   tmux capture-pane -p -e -t <pane> | node turn-state.mjs                  → working|queued|idle|unknown
 *   <raw owner tail bytes>            | node turn-state.mjs --stream         → same
 *   node turn-state.mjs submitted <transcript.jsonl> <fragment>             → exit 0 submitted / 1 not
 *   node turn-state.mjs lock <lockfile> <sessionId>                         → exit 0 free|stale / 3 held
 */
import { readFileSync, existsSync } from "node:fs"
import { resolve } from "node:path"
import { fileURLToPath } from "node:url"

const ANSI = /\x1b\[[0-9;?]*[A-Za-z]/g
// Observed glyphs: ✻ (U+273B), ✽ (U+273D), '*' ASCII; the wider set is the plausible rotation —
// a miss degrades to "idle" only from a tight glyph set, so the set stays conservative on purpose.
const GLYPH = "\\*\u2733\u2734\u2735\u2736\u2737\u2739\u273A\u273B\u273D\u273E\u2726\u2727\u2728\u00B7\u2742"
const SPINNER = new RegExp(`^ {0,2}[${GLYPH}] [A-Z][A-Za-z'’-]*ing…\\s*$`)
const QUEUE_HINT = "Press up to edit queued messages"

export function classifyScreen(screen) {
  const lines = String(screen ?? "").split(/\r?\n/).map((l) => l.replace(ANSI, ""))
  const spinner = lines.some((l) => SPINNER.test(l))
  const hint = lines.some((l) => l.includes(QUEUE_HINT))
  if (spinner && hint) return "queued"
  if (hint) return "queued"
  if (spinner) return "working"
  return "idle"
}

export function classifyStream(raw) {
  const s = String(raw ?? "")
  const window = s.slice(-800)
  if (!window.includes("❯\xa0") && !window.includes(QUEUE_HINT) && !SPINNER.test(window)) return "unknown"
  // The tail is a concatenation of row paints separated by \r — each segment is a line for matching.
  return classifyScreen(window.replace(/\r/g, "\n"))
}

/** The executor may clear only a seat whose turn is over — never a working or queued one. */
export const safeToClear = (state) => state === "idle"

/**
 * Submitted evidence: a user entry whose content is a plain string containing the fragment.
 * tool_results are type "user" but carry array content (the Read result contains the handoff body —
 * it must not confirm); queued commands and hook output leave no user entry at all (probe M2).
 */
export function transcriptSaysSubmitted(jsonlText, fragment) {
  for (const line of String(jsonlText ?? "").split(/\r?\n/)) {
    if (!line.includes(fragment)) continue
    try {
      const rec = JSON.parse(line)
      if (rec?.type === "user" && typeof rec?.message?.content === "string" && rec.message.content.includes(fragment)) return true
    } catch { /* not JSON — never evidence */ }
  }
  return false
}

/**
 * The fire lock: after typing /clear the watcher records {sid, at} for the pid; a later pass for
 * the SAME sessionId holds (the clear has not taken effect yet); once the record's sessionId
 * changed the clear happened and the lock is stale. Unreadable/absent lock ⇒ free (announced upstream).
 */
export function fireLockState(lockJson, sid, now = Date.now(), maxMs = 600_000) {
  if (!sid) return "held" // no id to verify against — hold rather than double-fire
  try {
    const lock = JSON.parse(lockJson)
    if (lock.sid !== sid) return "stale"
    return now - lock.at < maxMs ? "held" : "stale"
  } catch {
    return "free"
  }
}

/**
 * The fleet-owner path's turn state, from ACTIVITY instead of a screen window. Measured
 * 2026-09-21: the 800-byte window of classifyStream read `unknown` on a Mac seat — the prompt row
 * sat 1358 bytes back, behind clipboard (OSC 52) and update-banner paints, and the spinner arrives
 * as cell-positioned fragments, never a whole row. What does separate the states: a running turn
 * repaints its spinner continuously (5963 bytes in 3 s on a working seat) and an idle TUI writes
 * NOTHING (0 bytes on two idle seats). So: `delta` = growth of the owner's drained_total between
 * two reads ~2 s apart, `tail` = the last ~20 KB.
 *   delta > 0                                   → working (a turn, or a human typing — never type)
 *   no prompt row in the tail                   → unknown
 *   "Resume this session with" after the prompt → exited (the TUI quit; the pid can linger in the roster)
 *   otherwise                                   → idle
 */
export function classifyActivity(delta, tail) {
  if (delta === "" || delta == null) return "unknown"
  const d = Number(delta)
  if (!Number.isFinite(d)) return "unknown"
  if (d > 0) return "working"
  const t = String(tail ?? "")
  const prompt = t.lastIndexOf("❯\xa0")
  if (prompt < 0) return "unknown"
  if (t.lastIndexOf("Resume this session with") > prompt) return "exited"
  return "idle"
}

const invoked = process.argv[1] ? resolve(process.argv[1]) : ""
if (invoked === fileURLToPath(import.meta.url)) {
  const [cmd, a, b] = process.argv.slice(2)
  if (cmd === "submitted") {
    const text = a && existsSync(a) ? readFileSync(a, "utf8") : ""
    process.exit(transcriptSaysSubmitted(text, b) ? 0 : 1)
  }
  if (cmd === "lock") {
    let raw = ""
    try { raw = a && existsSync(a) ? readFileSync(a, "utf8") : "" } catch { /* free */ }
    const state = fireLockState(raw, b)
    console.log(state)
    process.exit(state === "held" ? 3 : 0)
  }
  let input = ""
  try { input = readFileSync(0, "utf8") } catch { /* no input ⇒ unknown */ }
  if (cmd === "activity") { console.log(classifyActivity(a, input)); process.exit(0) }
  console.log(process.argv.includes("--stream") ? classifyStream(input) : classifyScreen(input))
}
