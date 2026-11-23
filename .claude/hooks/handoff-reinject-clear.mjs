#!/usr/bin/env node
/**
 * handoff-reinject-clear — SessionStart hook (matchers: `clear` AND `compact`).
 *
 * WHAT THE FRESH CONTEXT RECEIVES (specs: clear-reload):
 * the latest manual handoff as POINTER + PREVIEW — path, ID, and a bounded excerpt — plus the
 * machine state page if one exists. The full file is deliberately NOT injected: hook output is
 * capped at 10 000 characters by the platform, and pointer + preview makes the cap ours by
 * choice instead of an overflow side effect. The fresh context reads the full file from disk.
 *
 * IDEMPOTENCY — PER EVENT, NOT PER SESSION. Measured 2026-09-12 in consumer-repo: a once-per-
 * session marker suppressed reinjection on later compacts of the same session (reinject
 * markers visible in only 4 of 17 compacts; one session compacted 4× in a day and could only
 * ever reinject once). So: this hook injects on `clear` and `compact` events only — never on
 * resume/startup/fork — and dedups same-event double-fires with a short time window, not a
 * permanent marker. A second compact an hour later MUST inject again.
 *
 * HONESTY RULES: the mtime choice is announced when several handoffs exist (the newest file
 * may be another thread's); truncation is loud and names the file; a `/clear` with nothing to
 * load says so — an unloaded context must never look loaded from the outside.
 *
 * A COMPACT WITHOUT AN OWN MARKER LOADS NOTHING BY MTIME. A compact keeps the session and its
 * summary; the newest handoff in the tree is, in a parallel-session tree, usually another
 * thread's (measured 2026-11-23: 80 of 141 watched sessions in one consumer tree never armed,
 * and every one of their native compacts was handed the tree's newest page as if it were
 * theirs). So on `compact` with no marker of THIS session the injection is a candidate LIST
 * (id, slug, age) and the instruction to rely on the compact summary — the session loads one
 * with `/handoff <ID>` only if it is its own. The clear path keeps an mtime fallback only where it
 * is no guess, because a cleared context has no summary to rely on: exactly one page of the cwd's
 * tree written in the last 2 h. Otherwise it lists the candidates too. The audit measured "newest
 * wins" reloading 10- and 35-day-old foreign pages.
 *
 * Hook input (stdin JSON): session_id, source (clear|compact|resume|startup|fork), cwd.
 * Output: SessionStart additionalContext JSON on stdout. Exit 0 ALWAYS — a hook must never
 * break the session's start; failure is announced in-chat or silent, never fatal.
 */
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"
import { execFileSync } from "node:child_process"
import { resolve } from "node:path"

const MAX_TOTAL = 10_000          // platform cap for hook output strings
const MAX_MANUAL = 7_000          // manual handoff preview budget
const MAX_AUTO = 2_300            // machine page budget (with headers, stays under the cap)
const DEDUP_WINDOW_MS = 120_000   // same-event double-fire guard — time-boxed, never permanent
const MARKER_PREFIX = ".written-" // same convention as the clear-gate's arm marker
const CLEAR_LINK_MS = 300_000     // how far back the watcher's typed /clear record may be
const FIRELOCK_MS = 900_000       // how long the watcher's `.firelock-<pid>` record is trusted

/**
 * Autopilot, optional (specs: intent-ledger, drift-guard). When the ledger module is installed
 * next to this hook (`./autopilot/`, or `../autopilot/` in the package tree), a clear records HOW
 * its handoff was chosen, binds the fresh session to the thread only for a marker-chosen reload,
 * and a bound session also receives the human's own words beside the handoff preview. Without
 * autopilot installed this hook behaves exactly as before.
 */
async function loadAutopilot() {
  for (const rel of ["./autopilot/ledger.mjs", "../autopilot/ledger.mjs"]) {
    const url = new URL(rel, import.meta.url)
    if (existsSync(fileURLToPath(url))) {
      try { return await import(url.href) } catch { return null }
    }
  }
  return null
}
const AP = await loadAutopilot()

/**
 * The line that stops a fresh session from adopting another lane. Measured 2026-09-25 in a
 * consumer repo: a docs session woke after an automatic clear and started offering fixes in a
 * bugfix lane its own handoff said belonged to another seat — the project's goal/priority file
 * had been injected beside the handoff, and the fresh context read it as a work queue.
 */
const OWN_THREAD =
  "**Your work is THIS handoff's thread** — continue its own next step. A project-wide goal, " +
  "priority or status file injected beside it is CONTEXT, not your work queue: an item assigned " +
  "to another seat or lane is not yours, even when it looks unclaimed. If this thread is blocked, " +
  "say so — do not take over another lane."

/** The compact-without-own-marker rule, verbatim — the regression test matches this sentence. */
export const NO_OWN_HANDOFF =
  "no own handoff for this session — rely on the compact summary; load one with /handoff <ID> only if it is yours"

/**
 * The lane guard for a context that loaded NO handoff: the work is the compact summary's thread,
 * and a listed handoff or a project goal file is context — the same measured lane takeover as
 * OWN_THREAD, worded for a session that has no handoff to call its own.
 */
const SUMMARY_THREAD =
  "**Your work is the thread in your compact summary.** The handoffs listed here and any project-wide " +
  "goal, priority or status file are CONTEXT, not your work queue: an item assigned to another seat or " +
  "lane is not yours, even when it looks unclaimed."

const MAX_CANDIDATES = 8
// A clear with no marker loads a page by mtime ONLY when that choice is not a guess: exactly one page
// in the cwd's own tree was written within this window. Measured failures of the old "newest wins"
// fallback (consumer audit 2026-11-23): one tree reloaded the same 35-day-old page 26 times into six
// unrelated sessions; another reloaded a 10-day-old foreign page on five manual clears; a third session
// adopted a foreign page and wrote to it 7 times. The 2 h is a judgement, not a measurement: a user who
// writes a handoff and clears does so within minutes, and the measured failures were days old.
const CLEAR_MTIME_MAX_AGE_MS = 2 * 60 * 60_000
const CLEAR_LIST_THREAD =
  "**No handoff is known to be yours.** If one of those listed is your thread, load it with " +
  "`/handoff <ID>`; otherwise start from the user's next message and re-measure state from the repo. " +
  "A handoff, goal or status file of another seat is CONTEXT, not your work queue."

/** `<ID>--<slug>.md` → {id, slug}; a name outside the convention keeps its whole stem as the slug. */
function idSlug(file) {
  const m = /^(\d{4}-[0-9a-f]{4})--(.+)\.md$/.exec(file)
  return m ? { id: m[1], slug: m[2] } : { id: null, slug: file.replace(/\.md$/, "") }
}

function age(ms) {
  const min = Math.max(0, Math.round(ms / 60_000))
  if (min < 60) return `${min} min`
  if (min < 48 * 60) return `${Math.round(min / 60)} h`
  return `${Math.round(min / 1440)} d`
}

function readEvent() {
  try { return JSON.parse(readFileSync(0, "utf8")) } catch { return {} }
}

function cut(text, max, path) {
  if (text.length <= max) return text
  return `${text.slice(0, max)}\n\n… (truncated — full page: \`${path}\`, ${text.length} chars — READ IT before working)`
}

function session8(sessionId) {
  return String(sessionId ?? "").replace(/[^a-zA-Z0-9]/g, "").slice(0, 8) || "ismeretlen"
}

/**
 * Candidate handoff dirs: the session's cwd tree FIRST, then every sibling worktree's
 * (9.1, measured 2026-09-13: a manual clear of the consumer's worktree agent reloaded the MAIN
 * repo's newest handoff — a different thread — because the tree was resolved from the hook's
 * install location instead of the thread). Enumerating worktrees is what makes the
 * marker-based choice below able to find the thread wherever in the fan it wrote its handoff.
 */
export function candidateHandoffDirs(startDir) {
  const dirs = [startDir]
  try {
    const out = execFileSync("git", ["-C", dirname(startDir), "worktree", "list", "--porcelain"], { encoding: "utf8" })
    for (const m of out.matchAll(/^worktree (.+)$/gm)) dirs.push(join(m[1], ".set/handoff"))
  } catch { /* not a git tree (or no git) — the cwd tree alone */ }
  return [...new Set(dirs)]
}

/** The handoff THIS session armed with, if its marker still names an existing file. */
function markerChoice(dirs, s8) {
  if (s8 === "ismeretlen") return null
  for (const dir of dirs) {
    const mp = join(dir, MARKER_PREFIX + s8)
    if (!existsSync(mp)) continue
    try {
      const name = readFileSync(mp, "utf8").trim().split(/\s+/)[1]
      if (name && existsSync(join(dir, name))) return { dir, file: name }
    } catch { /* unreadable marker — fall through to mtime */ }
  }
  return null
}

export function buildInjection({ dir, source, now = Date.now(), sessionId = "", prevSessionId = "" }) {
  if (source !== "clear" && source !== "compact") return null // per-event allowlist

  const s8 = session8(sessionId)
  const prev8 = prevSessionId ? session8(prevSessionId) : null
  const dirs = candidateHandoffDirs(dir).filter((d) => existsSync(d))

  if (dirs.length === 0) return source === "clear"
    ? plain("No handoff directory found — this cleared context starts with nothing loaded. If a thread was open here, it was not written down.")
    : null

  // Resolution order: the session's OWN marker across ALL candidate trees (it names the exact
  // file this session armed with), then newest-by-mtime of the CWD's OWN tree — loudly
  // announced as the heuristic it is. Merging the other trees into the mtime fallback was
  // MEASURED harmful on 2026-09-13: the bugfix pane (cwd = main tree, no marker reachable by
  // its fresh id) got a sibling worktree's newer page as its reload. Other trees' pages stay
  // REACHABLE — listed by full path — but never become the primary choice by recency.
  //
  // After a clear the fresh session has a NEW id, so its own marker cannot exist yet. For an
  // AUTOMATIC clear the watcher logged which session it cleared (probe M3, 2.1.270: the platform
  // offers no pointer to the predecessor) — that session's marker names the thread's handoff.
  const ownMarked = markerChoice(dirs, s8)
  const prevMarked = !ownMarked && source === "clear" && prev8 ? markerChoice(dirs, prev8) : null
  const marked = ownMarked ?? prevMarked

  // Manual handoffs (not the machine `--allapot.md` pages) — all trees, newest first, for
  // the listing; the fallback CHOICE below reads only the cwd's own tree.
  const manual = dirs.flatMap((d) =>
    readdirSync(d)
      .filter((f) => f.endsWith(".md") && !f.endsWith("--allapot.md"))
      .map((f) => ({ dir: d, f, m: statSync(join(d, f)).mtimeMs })),
  ).sort((a, b) => b.m - a.m)

  const homeManual = manual.filter((k) => k.dir === dir)
  // A compact with no marker of THIS session picks nothing: the newest page is a guess, and a compact
  // has its own summary to fall back on (see the header). A clear picks by mtime only when it is NOT a
  // guess: exactly one page of the cwd's own tree is recent (CLEAR_MTIME_MAX_AGE_MS). Several recent
  // pages, or only old ones, give the candidate list instead.
  const recentHome = homeManual.filter((k) => now - k.m <= CLEAR_MTIME_MAX_AGE_MS)
  const mtimeOk = source === "clear" && recentHome.length === 1
  const listOnly = !marked && !mtimeOk && manual.length > 0
  const chosen = marked ?? (mtimeOk ? { dir: recentHome[0].dir, file: recentHome[0].f } : null)

  // Autopilot: record how the handoff was chosen, bind only a marker-chosen reload, and give a
  // bound session the thread's human direction verbatim. `clear` alone writes the reload record —
  // a compact keeps the session id and its existing binding.
  let charter = ""
  let autopilotNote = ""
  if (AP && s8 !== "ismeretlen") {
    const chosenId = chosen ? AP.handoffIdOf(chosen.file) : null
    if (source === "clear") {
      AP.writeReload(dir, sessionId, {
        choice: marked ? "marker" : chosen ? "mtime" : "none", id: chosenId, prev: prev8,
        markerOf: ownMarked ? "own" : prevMarked ? "previous-session" : null,
      })
      if (marked && chosenId) AP.bindSession(dir, sessionId, chosenId)
    }
    const thread = AP.threadOf(dir, sessionId)
    const unbound = !thread.bound || (thread.reload && thread.reload.choice !== "marker")
    if (!unbound) {
      charter = AP.charterBlock(AP.readThread(dir, thread.id), AP.loadConfig(dirname(dirname(dir))).charterChars)
    } else if (source === "clear") {
      autopilotNote = `⚠ Autopilot: this session is NOT bound to a thread (${thread.via}) — no automatic continuation and no automatic answers until a human loads a handoff with \`/handoff <ID>\`.`
    }
  }

  const parts = []
  let used = 0

  if (chosen) {
    const p = join(chosen.dir, chosen.file)
    let body = ""
    try { body = readFileSync(p, "utf8") } catch { body = null }
    const shown = chosen.dir === dir ? `.set/handoff/${chosen.file}` : p
    const reason = ownMarked
      ? "chosen by THIS session's own arm marker — the thread you wrote before the clear"
      : prevMarked
        ? "chosen by the arm marker of the session this automatic clear replaced — the thread written before the clear"
        : "chosen by mtime: the only page of this tree written in the last 2 h — in a parallel-session tree, verify it is YOURS"
    const others = manual.filter((k) => !(k.dir === chosen.dir && k.f === chosen.file))
    parts.push([
      `## ⚠ Fresh context — handoff reloaded (${source})`,
      "",
      `**Handoff: \`${shown}\`** (${reason}).`,
      others.length > 0 ? `Other live handoffs: ${others.slice(0, 6).map((k) => (k.dir === dir ? `.set/handoff/${k.f}` : join(k.dir, k.f))).join(", ")}.` : "",
      OWN_THREAD,
      autopilotNote,
      charter,
      "",
      body == null
        ? `⚠ The handoff file exists but is UNREADABLE — open it by hand before working.`
        : cut(body, Math.min(MAX_MANUAL - charter.length, MAX_TOTAL - used - 400 - charter.length), p),
      "",
    ].filter((s) => s !== "").join("\n"))
    used += parts[0].length
  } else if (listOnly) {
    const rows = manual.slice(0, MAX_CANDIDATES).map((k) => {
      const { id, slug } = idSlug(k.f)
      const where = k.dir === dir ? `.set/handoff/${k.f}` : join(k.dir, k.f)
      return `- ${id ? `\`${id}\`` : "(no ID)"} · ${slug} · ${age(now - k.m)} old · \`${where}\``
    })
    const why = source === "clear"
      ? (recentHome.length > 1
        ? `${recentHome.length} pages of this tree were written in the last 2 h, so the newest is a guess; none was loaded.`
        : "No page of this tree was written in the last 2 h; an old page is another thread's as often as yours. None was loaded.")
      : "This session has no arm marker, so no handoff here is known to be its own; none was chosen by recency."
    parts.push([
      source === "clear" ? "## ⚠ Fresh context — no handoff loaded" : "## Context compacted — no handoff loaded",
      "",
      source === "clear" ? "**No arm marker names this session's thread.**" : `**${NO_OWN_HANDOFF}.**`,
      why,
      "",
      `Handoffs in this tree (newest first${manual.length > MAX_CANDIDATES ? `, ${MAX_CANDIDATES} of ${manual.length}` : ""}):`,
      ...rows,
      "",
      source === "clear" ? CLEAR_LIST_THREAD : SUMMARY_THREAD,
      source === "clear" ? autopilotNote : "",
      "",
    ].filter((x, i, a) => x !== "" || a[i - 1] !== "").join("\n"))
    used += parts[0].length
  } else if (source === "clear") {
    parts.push([
      "## ⚠ Fresh context — NOTHING to load",
      "",
      "No handoff exists in this repository or its worktrees. If a work thread was open before the clear, it was not written down; proceed carefully and re-measure state from the repo.",
      OWN_THREAD,
      autopilotNote,
      "",
    ].join("\n"))
    used += parts[0].length
  }

  // The machine page (PreCompact hook output), if present — secondary, smaller frame.
  const latestPtr = join(dir, ".latest")
  if (existsSync(latestPtr)) {
    try {
      const name = readFileSync(latestPtr, "utf8").trim()
      const p = join(dir, name)
      if (name && existsSync(p)) {
        const auto = cut(readFileSync(p, "utf8"), Math.max(0, Math.min(MAX_AUTO, MAX_TOTAL - used - 200)), p)
        if (auto.trim()) parts.push(`### Machine state page (hook-written — numbers, not intent)\n\n${auto}`)
      }
    } catch { /* a bad pointer must not take the injection down */ }
  }

  return parts.length ? parts.join("\n") : null
}

function plain(text) {
  return text
}

function emit(text) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: "SessionStart", additionalContext: text },
  }))
}

/** Same-event double-fire guard, exported for the regression test of the measured bug. */
export function sameEventDoubleFire(dedupPath, now = Date.now(), windowMs = DEDUP_WINDOW_MS) {
  return existsSync(dedupPath) && now - statSync(dedupPath).mtimeMs < windowMs
}

/** The `claude` process this hook runs under: walk the parent chain to a runtime session record. */
function claudePid() {
  let p = process.pid
  for (let i = 0; i < 12 && p > 1; i++) {
    if (existsSync(join(homedir(), ".claude", "sessions", `${p}.json`))) return p
    try {
      const stat = readFileSync(`/proc/${p}/stat`, "utf8")
      p = Number(stat.slice(stat.lastIndexOf(")") + 2).split(" ")[1])
    } catch {
      // No /proc (macOS): ask ps, which both platforms have.
      try { p = Number(execFileSync("ps", ["-o", "ppid=", "-p", String(p)], { encoding: "utf8" }).trim()) }
      catch { return null }
    }
  }
  return null
}

/**
 * The session an AUTOMATIC clear replaced. Probe M3 (2.1.270): the SessionStart(clear) payload
 * carries only the new id, and the runtime record is already rewritten when the hook runs — so
 * the watcher records which session it cleared, keyed by the claude pid, and this reads it back.
 * TWO records carry the same fact, and both are read: the autopilot ledger (`typed.jsonl`) when
 * autopilot is installed, and `.firelock-<pid>` which the watcher writes in EVERY install. A
 * manual clear leaves neither and binds nothing (announced in the injection as an mtime guess).
 */
export function previousSessionOf(dir, pid, now = Date.now()) {
  if (!pid) return ""
  if (AP) {
    const rec = AP.readJsonl(join(dir, "typed.jsonl"))
      .filter((r) => r.kind === "clear" && r.pid === String(pid) && now - Date.parse(r.at) < CLEAR_LINK_MS)
      .pop()
    if (rec?.session8) return rec.session8
  }
  // Without autopilot installed the ledger does not exist — but the watcher writes the same
  // fact to `.firelock-<pid>` ({sid, at}) on every automatic clear, in the tree it cleared.
  // MEASURED 2026-09-25: with the ledger absent this function returned "" for EVERY automatic
  // clear, so the previous session's marker was never consulted and the reload fell through to
  // mtime — handing a fresh session whichever seat wrote last. The fallback is the same record,
  // read from the file the watcher already writes.
  for (const d of candidateHandoffDirs(dir)) {
    try {
      const rec = JSON.parse(readFileSync(join(d, `.firelock-${pid}`), "utf8"))
      if (rec?.sid && now - Number(rec.at) < FIRELOCK_MS) return String(rec.sid)
    } catch { /* no or unreadable lock in this tree — try the next */ }
  }
  return ""
}

function main() {
  const ev = readEvent()
  const dir = process.env.HANDOFF_DIR ?? join(ev.cwd ?? process.cwd(), ".set/handoff")
  const prevSessionId = ev.source === "clear" ? previousSessionOf(dir, claudePid()) : ""
  const injection = buildInjection({ dir, source: ev.source, now: Date.now(), sessionId: ev.session_id, prevSessionId })
  if (!injection) return

  // Same-event double-fire guard: a marker per session+source, honored only inside the window.
  // Past the window it is ignored — that is what makes a later compact inject again.
  const s8 = String(ev.session_id ?? "").replace(/[^a-zA-Z0-9]/g, "").slice(0, 8) || "x"
  const dedup = join(dir, `.injected-${s8}-${ev.source}`)
  if (sameEventDoubleFire(dedup)) return
  try { writeFileSync(dedup, new Date().toISOString() + "\n") } catch { /* worst case: one duplicate */ }

  emit(injection)
}

// Run only when invoked as the hook itself — importing this module (the tests do) must never
// touch stdin, which would block the importer forever.
const invoked = process.argv[1] ? resolve(process.argv[1]) : ""
if (invoked === fileURLToPath(import.meta.url)) {
  try { main() } catch { /* never break the session start */ }
  process.exit(0)
}
