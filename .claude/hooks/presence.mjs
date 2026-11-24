#!/usr/bin/env node
/**
 * presence — is a human typing on this session's input line right now? (autopilot task group 0)
 *
 * WHY: at the 10:03:50Z automatic clear (2026-09-13) the human was typing in the pane. The idle
 * gate reads the transcript, and typing without submitting leaves no trace there — so the
 * watcher's `/clear` landed inside the half-written line ("…we don1t need opu/clear"), and the
 * continue prompt fused with the human's words. The executor must look at the INPUT LINE itself.
 *
 * THE RULE (measured live on Claude Code 2.1.270):
 *   the input row starts with "❯" + U+00A0 (no-break space) — scrollback rows and a dialog's
 *   cursor carry no U+00A0, so the LAST such occurrence is the input line. What follows it:
 *     nothing / spaces / colour resets / erase-line  → empty
 *     starts with SGR 2 (dim, \x1b[2m)               → ghost: a client suggestion or placeholder
 *     anything else                                  → typed: a human is writing — DO NOT TYPE
 *   tmux: `capture-pane -p -e` (a plain capture shows a ghost suggestion exactly like typed text).
 *   fleet owner path: ownerd offers only raw output bytes (`tail`); measured on live tails, the
 *   input row is painted as `❯\xa0` + content up to the next `\r` — the same rule applies to that
 *   last paint (`--stream`). NOT measured: whether keystrokes are echoed as incremental cursor
 *   writes instead of a row repaint, multi-line input, a theme change.
 *   No input row found ⇒ `unknown`, and the executor treats unknown as "do not type".
 *
 * Usage: tmux capture-pane -p -e -t <pane> | node presence.mjs            → empty|ghost|typed|unknown
 *        <raw owner tail bytes>             | node presence.mjs --stream
 *        … | node presence.mjs [--stream] --explain   → "typed" becomes typed[paint <shape>] (shapeOf)
 */
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { fileURLToPath } from "node:url"

const PROMPT = "❯\xa0"
const LEAD = /^(?:\x1b\[(?:0|39|49|22)?m|\x1b\[K)*/
const ANY_CSI = /\x1b\[[0-9;?]*[A-Za-z]/g
// Everything else that paints nothing: OSC titles (ESC ] … BEL/ST), charset selects (ESC ( B),
// other two-byte escapes, and C0 controls such as SI (\x0f). Measured 2026-11-24 on a fleet seat:
// a freshly cleared session's empty input row was painted as cursor moves + `ESC ( B` + `\x0f`,
// and with only CSI stripped that read as "typed", so the auto-continue was held as "a human is at
// the keyboard" and the cleared session sat idle.
const NON_PRINTING = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()*+][0-9A-Za-z]|\x1b[=>78DEHMNOZc]|[\x00-\x08\x0b-\x1f\x7f]/g
const visible = (t) => t.replace(ANY_CSI, "").replace(NON_PRINTING, "")

/** Classify what follows the input prompt glyph. */
export function classifyAfterPrompt(after) {
  const s = String(after ?? "")
  const rest = s.slice(LEAD.exec(s)[0].length)
  if (visible(rest).trim() === "") return "empty"
  if (rest.startsWith("\x1b[2m")) return "ghost"
  return "typed"
}

/** What follows the prompt on the last input row of a rendered screen (tmux capture-pane -p -e), or null. */
function inputRowOf(screen) {
  const rows = String(screen ?? "").split(/\r?\n/)
  for (let i = rows.length - 1; i >= 0; i--) {
    const at = rows[i].lastIndexOf(PROMPT)
    if (at >= 0) return rows[i].slice(at + PROMPT.length)
  }
  return null
}

/** What follows the prompt in the last paint of the input row of a raw stream (ownerd tail), or null. */
function inputPaintOf(raw) {
  const s = String(raw ?? "")
  const at = s.lastIndexOf(PROMPT)
  if (at < 0) return null
  const tail = s.slice(at + PROMPT.length)
  const end = tail.search(/[\r\n]/)
  return end < 0 ? tail : tail.slice(0, end)
}

/** A rendered screen (tmux capture-pane -p -e): the last row carrying the input prompt. */
export function classifyInputRow(screen) {
  const after = inputRowOf(screen)
  return after == null ? "unknown" : classifyAfterPrompt(after)
}

/** A raw terminal byte stream (ownerd tail): the last paint of the input row, up to its \r or \n. */
export function classifyStream(raw) {
  const after = inputPaintOf(raw)
  return after == null ? "unknown" : classifyAfterPrompt(after)
}

/**
 * The SHAPE of an input-row paint, for the log when it reads "typed": every escape sequence kept
 * as written (\e[…), every run of visible text replaced by its length ‹n› — never the text, which
 * may be a human's unsent draft. Why: on 2026-11-24 a fleet seat read "typed" for 34 min with
 * nobody typing (12:12→12:46Z, until a browser viewer re-attached), the raw stream was gone by the
 * time anyone looked, and nothing recorded what the check had seen.
 */
export function shapeOf(after) {
  const TOKEN = /\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()*+][0-9A-Za-z]|\x1b[=>78DEHMNOZc]|[\x00-\x1f\x7f]/g
  const out = []
  let last = 0
  const text = (t) => { const n = [...t].length; if (n) out.push(`‹${n}›`) }
  for (const m of String(after ?? "").matchAll(TOKEN)) {
    text(String(after).slice(last, m.index))
    const e = m[0]
    out.push(e.startsWith("\x1b]") ? "\\e]…" : e.startsWith("\x1b") ? "\\e" + e.slice(1) : `\\x${e.charCodeAt(0).toString(16).padStart(2, "0")}`)
    last = m.index + e.length
  }
  text(String(after ?? "").slice(last))
  return out.length > 40 ? out.slice(0, 40).join("") + "…" : out.join("")
}

/** The executor may type only into an empty line or over a ghost suggestion (typing replaces it). */
export const safeToType = (state) => state === "empty" || state === "ghost"

const invoked = process.argv[1] ? resolve(process.argv[1]) : ""
if (invoked === fileURLToPath(import.meta.url)) {
  let input = ""
  try { input = readFileSync(0, "utf8") } catch { /* no input ⇒ unknown */ }
  const stream = process.argv.includes("--stream")
  const state = stream ? classifyStream(input) : classifyInputRow(input)
  // --explain: a "typed" verdict carries the paint's shape, so the log can show what was seen.
  if (state === "typed" && process.argv.includes("--explain")) {
    console.log(`typed[paint ${shapeOf(stream ? inputPaintOf(input) : inputRowOf(input))}]`)
  } else console.log(state)
}
