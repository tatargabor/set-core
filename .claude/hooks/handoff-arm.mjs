#!/usr/bin/env node
/**
 * handoff-arm — PostToolUse hook (`Write|Edit|MultiEdit|Bash`): arms THIS session for the
 * automatic /clear when it writes a handoff sheet that passes a structural check.
 *
 * WHY IT SHIPS: the clear gate refuses every session without a `.written-<session8>` marker, and
 * until now nothing in the package wrote one — each consumer had to build its own arming hook.
 * A project without one (measured 2026-09-21: a fresh project would have run the watcher for
 * ever with "marker: no marker for this session") never gets cleared at all.
 *
 * WHY BASH TOO: a sheet written with a heredoc never reaches a Write/Edit hook. Measured the same
 * day on a consumer seat: the session sat at "Ready for /clear" and the watcher refused it every
 * minute. For Bash, a candidate is a handoff path the command NAMES and that was modified in the
 * last 15 s — a command that only READS a sheet must not arm anything.
 *
 * The check is structural, not a judgement of quality: the header with an ID, and every section
 * heading the /handoff skill prescribes (0–7). A project with its own content check keeps using
 * it and does not install this hook. A failing write REMOVES an existing marker (armMarker with
 * passed:false) — a rewrite that broke the sheet must not leave the session armed on the old one.
 */
import { appendFileSync, existsSync, mkdirSync, readFileSync, statSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { armMarker } from "./clear-gate.mjs"

const SHEET = /\.set\/handoff\/\d{4}-[0-9a-f]{4}--[^/]*\.md$/
const SECTIONS = ["0", "1", "2", "3", "4", "5", "6", "7"]

/** What the sheet lacks, as human-readable items — empty means it passes. */
export function missingParts(text) {
  const missing = []
  if (!/^# HANDOFF: .*ID: \d{4}-[0-9a-f]{4}/m.test(text)) missing.push("the `# HANDOFF: <slug> — <date> · ID: <ID>` header")
  for (const n of SECTIONS) if (!new RegExp(`^## ${n}\\. `, "m").test(text)) missing.push(`section \`## ${n}.\``)
  return missing
}

/** Bash: the handoff sheet the command names AND that changed in the last windowMs. */
export function bashHandoffTarget(command, cwd, now = Date.now(), windowMs = 15_000) {
  const hits = String(command ?? "").match(/[^\s"'<>|;&()=]*\.set\/handoff\/[^\s"'<>|;&()=]*\.md/g) ?? []
  for (const raw of [...new Set(hits)]) {
    const p = resolve(cwd || process.cwd(), raw)
    try {
      if (SHEET.test(p) && now - statSync(p).mtimeMs <= windowMs) return p
    } catch { /* a glob or an unexpanded variable — not a candidate */ }
  }
  return ""
}

export function targetOf(ev, now = Date.now()) {
  const file = ev?.tool_name === "Bash"
    ? bashHandoffTarget(ev?.tool_input?.command, ev?.cwd, now)
    : resolve(ev?.cwd || process.cwd(), ev?.tool_input?.file_path || "")
  return SHEET.test(file) ? file : ""
}

function log(dir, line) {
  try { mkdirSync(dir, { recursive: true }); appendFileSync(join(dir, "auto-clear.log"), `${new Date().toISOString()} ${line}\n`) } catch { /* the log is not the critical path */ }
}

/**
 * A sheet whose NAME breaks the convention is never armed, and that used to be silent. Measured
 * 2026-11-23: a page written as `1102-n8gt--….md` (an ID typed by hand, not from `openssl rand`) left its
 * session unarmed for two days, and nothing said why. So a Write/Edit to a direct child of .set/handoff/
 * whose body starts like a handoff, but whose name does not match, is announced. Research notes parked
 * there (no `# HANDOFF` header) and machine pages stay quiet.
 */
export function misnamedSheet(ev) {
  if (ev?.tool_name === "Bash") return ""
  const p = resolve(ev?.cwd || process.cwd(), ev?.tool_input?.file_path || "")
  if (!/\.set\/handoff\/[^/]+\.md$/.test(p) || /--allapot\.md$/.test(p) || SHEET.test(p)) return ""
  try { return /^# HANDOFF/.test(readFileSync(p, "utf8").trimStart()) ? p : "" } catch { return "" }
}

function warnMisnamed(ev) {
  const p = misnamedSheet(ev)
  if (!p) return 0
  const name = p.replace(/^.*\//, "")
  log(dirname(p), `skip  ${ev.session_id ?? "?"}  ${name} is not a handoff path (ID must be <MMDD>-<4 hex>) — NOT armed`)
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: "PostToolUse",
    additionalContext: `⚠ ${name} is NOT armed for auto-clear: a handoff file must be named \`<MMDD>-<4 hex>--<slug>.md\`, with the ID taken from ` +
      "the command (`date +%m%d` and `openssl rand -hex 2`), never typed by hand. Rename it with the right ID (and fix the header's `ID:`), then write it again with Write or Edit." } }) + "\n")
  return 0
}

async function main() {
  let input = ""
  for await (const chunk of process.stdin) input += chunk
  let ev
  try { ev = JSON.parse(input) } catch { return 0 } // a hook error must never break the work
  const file = targetOf(ev)
  if (!file) return warnMisnamed(ev)
  if (!existsSync(file) || !ev.session_id) return 0
  const dir = dirname(file) // the marker lives beside the sheet — the gate reads the session's own tree
  const missing = missingParts(readFileSync(file, "utf8"))
  const r = armMarker(dir, ev.session_id, file, { passed: missing.length === 0 })
  if (r.wrote) {
    log(dir, `arm   ${ev.session_id}  ${file.replace(/^.*\//, "")} passed the structural check (${ev.tool_name})`)
    return 0
  }
  log(dir, `unarm ${ev.session_id}  ${file.replace(/^.*\//, "")} is missing: ${missing.join(", ")}`)
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: `⚠ The handoff ${file.replace(/^.*\//, "")} is NOT armed for auto-clear — it is missing: ${missing.join("; ")}. ` +
        "Add them now, in the same file, with the Edit tool. An empty section still needs its heading and a \"none\" line.",
    },
  }) + "\n")
  return 0
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(await main())
}
