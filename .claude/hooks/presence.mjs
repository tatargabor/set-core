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
 */
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { fileURLToPath } from "node:url"

const PROMPT = "❯\xa0"
const LEAD = /^(?:\x1b\[(?:0|39|49|22)?m|\x1b\[K)*/
const ANY_CSI = /\x1b\[[0-9;?]*[A-Za-z]/g

/** Classify what follows the input prompt glyph. */
export function classifyAfterPrompt(after) {
  const s = String(after ?? "")
  const rest = s.slice(LEAD.exec(s)[0].length)
  if (rest.replace(ANY_CSI, "").trim() === "") return "empty"
  if (rest.startsWith("\x1b[2m")) return "ghost"
  return "typed"
}

/** A rendered screen (tmux capture-pane -p -e): the last row carrying the input prompt. */
export function classifyInputRow(screen) {
  const rows = String(screen ?? "").split(/\r?\n/)
  for (let i = rows.length - 1; i >= 0; i--) {
    const at = rows[i].lastIndexOf(PROMPT)
    if (at >= 0) return classifyAfterPrompt(rows[i].slice(at + PROMPT.length))
  }
  return "unknown"
}

/** A raw terminal byte stream (ownerd tail): the last paint of the input row, up to its \r or \n. */
export function classifyStream(raw) {
  const s = String(raw ?? "")
  const at = s.lastIndexOf(PROMPT)
  if (at < 0) return "unknown"
  const tail = s.slice(at + PROMPT.length)
  const end = tail.search(/[\r\n]/)
  return classifyAfterPrompt(end < 0 ? tail : tail.slice(0, end))
}

/** The executor may type only into an empty line or over a ghost suggestion (typing replaces it). */
export const safeToType = (state) => state === "empty" || state === "ghost"

const invoked = process.argv[1] ? resolve(process.argv[1]) : ""
if (invoked === fileURLToPath(import.meta.url)) {
  let input = ""
  try { input = readFileSync(0, "utf8") } catch { /* no input ⇒ unknown */ }
  console.log(process.argv.includes("--stream") ? classifyStream(input) : classifyInputRow(input))
}
