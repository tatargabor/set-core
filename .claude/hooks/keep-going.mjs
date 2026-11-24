#!/usr/bin/env node
/**
 * keep-going — the session does not stop until it has a real reason to (opt-in).
 *
 * Two modes, one file:
 *   node keep-going.mjs stop [--threshold N] [--max N]   Stop hook
 *   node keep-going.mjs post [--threshold N]             PostToolUse hook (matcher "*")
 *   --headless  also act on `claude -p` runs (default: only interactive sessions)
 *
 * THE RULE (user, 2026-09-21): a session keeps working and stops only on a concrete question it
 * cannot answer itself. When it reaches the context limit, it writes a handoff, and the auto-clear
 * watcher clears it and continues it from that handoff. This hook is the "keeps working" and the
 * "writes a handoff" half; clear-gate + watch-auto-clear are the rest.
 *
 * Stop decisions, in order — each one logged to .set/handoff/keep-going.log:
 *   1. kill switch (.no-keepgoing / .no-keepgoing-<session8>)          → allow the stop
 *   2. background tasks running (their notification wakes the session) → allow
 *   3. the last message has a line `NEED INPUT:` or `ALL DONE:`         → allow
 *   4. context ≥ threshold:
 *        a fresh arm marker for this session (≤ 30 min)  → allow: the watcher clears it now
 *        otherwise → BLOCK: "write the handoff now"      (at most 3 times, then allow + log)
 *   5. continuation budget: consecutive blocks since the last HUMAN prompt ≥ max → allow + log
 *   6. otherwise → BLOCK: "continue with the next step"
 *
 * The budget is what keeps this from running away: it counts only this hook's own nudges and
 * resets on the next human prompt. A human prompt is a `user` entry whose content is text and
 * that is not `isMeta` — measured 2026-09-21: a Stop hook's block reason lands in the transcript
 * as a `user` entry WITH `isMeta: true`, so the hook's own nudges never reset its own budget.
 * The watcher's auto-continue prompt is typed, so it does count as human — correct: after a
 * clear it is a fresh session with a fresh budget anyway.
 */
import { appendFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { readTokens, session8, markerFreshness, tailLines, DEFAULT_THRESHOLD } from "./clear-gate.mjs"

// threshold: the clear-gate's own default (400k, owner decision 2026-11-23) — keep the two equal.
// threshold: the gate's own constant, imported, so the two cannot drift apart (they did: consumer
// settings still carried --threshold 500000 after the gate moved to 400k).
export const DEFAULTS = { threshold: DEFAULT_THRESHOLD, max: 40, markerFreshMs: 30 * 60_000, handoffNudges: 3, postEveryMs: 10 * 60_000 }
const STOP_MARK = /^[\s>*_`-]*(NEED INPUT|ALL DONE)\s*:/im

/** The last assistant text of the transcript — the fallback when the Stop input lacks it. */
export function lastAssistantText(lines) {
  for (let i = lines.length - 1; i >= 0; i--) {
    let e; try { e = JSON.parse(lines[i]) } catch { continue }
    if (e.type !== "assistant") continue
    const parts = Array.isArray(e.message?.content) ? e.message.content : []
    const text = parts.filter((p) => p.type === "text").map((p) => p.text).join("\n")
    if (text.trim()) return text
  }
  return ""
}

/** The uuid of the last HUMAN prompt: a non-meta user entry carrying text, not a tool result. */
export function lastHumanPrompt(lines) {
  for (let i = lines.length - 1; i >= 0; i--) {
    let e; try { e = JSON.parse(lines[i]) } catch { continue }
    if (e.type !== "user" || e.isMeta) continue
    const c = e.message?.content
    const text = typeof c === "string" ? c
      : Array.isArray(c) && c.every((p) => p.type === "text") ? c.map((p) => p.text).join("\n") : ""
    if (!text.trim() || text.trimStart().startsWith("<")) continue // tool results, command/caveat wrappers
    // this hook's own nudge, however the runtime marks it: counted as human, it would reset the budget
    if (text.trimStart().startsWith("[keep-going")) continue
    return e.uuid ?? e.timestamp ?? String(i)
  }
  return null
}

function readState(path) { try { return JSON.parse(readFileSync(path, "utf8")) } catch { return {} } }

/**
 * The Stop decision as a pure function of what the hook can see — the tests drive this directly.
 * Returns { block: boolean, reason?: string, why: string, state }.
 */
export function decideStop({ message, backgroundTasks = [], tokens, markerAgeMs, markerFresh, killed, human, state = {}, opts = {}, autoClear = true }) {
  const o = { ...DEFAULTS, ...opts }
  // `?? null` on both sides so an empty state and "no human prompt found" compare equal; the
  // stored state carries `human` forward, so a budget with no human prompt still runs out (tested).
  const st = (state.human ?? null) === (human ?? null) ? { ...state } : { human, count: 0, handoffNudges: 0 }
  if (killed) return { block: false, why: `kill switch (${killed})`, state: st }
  if (backgroundTasks.length) return { block: false, why: `${backgroundTasks.length} background task(s) running — their notification wakes the session`, state: st }
  const mark = STOP_MARK.exec(message ?? "")
  if (mark) return { block: false, why: `the message says ${mark[1].toUpperCase()}`, state: st }
  // The handoff demand exists for the auto-clear watcher to act on. Without one, it would keep a
  // session writing handoffs nobody clears (consumer review 2026-11-08, M5), so only the continue rule runs.
  if (autoClear && tokens != null && tokens >= o.threshold) {
    // Fresh = the gate's definition (the handoff was the last act) when the caller measured it; the
    // age rule is only the fallback. A handoff 20 min old with 20 min of work after it is NOT fresh:
    // the gate would refuse the clear, so the stop must not wait for one.
    const fresh = markerFresh ?? (markerAgeMs != null && markerAgeMs <= o.markerFreshMs)
    if (fresh) return { block: false, why: `context ${tokens} ≥ ${o.threshold} and the handoff is armed — waiting for the auto-clear`, state: st }
    if ((st.handoffNudges ?? 0) >= o.handoffNudges) return { block: false, why: `context ${tokens} ≥ ${o.threshold}, asked ${st.handoffNudges}× for a handoff and none is armed — stopping so a human sees it`, state: st }
    st.handoffNudges = (st.handoffNudges ?? 0) + 1
    return {
      block: true, state: st, why: `context ${tokens} ≥ ${o.threshold}, no fresh armed handoff — handoff nudge ${st.handoffNudges}/${o.handoffNudges}`,
      reason: `[keep-going] Context is at ${tokens} tokens (limit ${o.threshold}). Write the handoff NOW: run /handoff and write the sheet with the Write or Edit tool (never Bash). ` +
        `Include every section, and state background work as "none left" if nothing runs. Then end your turn — the auto-clear watcher clears this session and continues it from the handoff.`,
    }
  }
  if ((st.count ?? 0) >= o.max) return { block: false, why: `continuation budget spent (${st.count}/${o.max} since the last human prompt) — stopping so a human sees it`, state: st }
  st.count = (st.count ?? 0) + 1
  return {
    block: true, state: st, why: `continue ${st.count}/${o.max}`,
    reason: `[keep-going ${st.count}/${o.max}] Do not stop here — continue with the next step of the current work (the loaded handoff's next steps, if there is one). ` +
      "Do not ask permission-style questions (\"Want me to…?\", \"Shall I…?\"): if the task or the human's earlier words already cover the step, do it. " +
      "The exception: an outward, irreversible or permission step (sending a mail, a push, publishing, a deletion, a payment, filling an approval field) is never covered by earlier words; ask it with a `NEED INPUT:` line. " +
      "Stop only when (a) you need a concrete decision from the human that nothing earlier answers — put it on its own line starting with `NEED INPUT:` — or " +
      "(b) everything is finished — start a line with `ALL DONE:`.",
  }
}

function parseArgs(argv) {
  const o = {}
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--threshold") o.threshold = Number(argv[++i])
    else if (argv[i] === "--max") o.max = Number(argv[++i])
    else if (argv[i] === "--headless") o.headless = true
  }
  return o
}

// The project, not the shell's cwd: a session that cd's into a subdirectory or a sibling keeps its
// kill switch, state and budget (consumer review 2026-11-08, M3). CLAUDE_PROJECT_DIR is what the
// runtime sets for hooks; ev.cwd is only the fallback.
function projectDir(ev) { return process.env.CLAUDE_PROJECT_DIR || ev.cwd || process.cwd() }
export const HEARTBEAT_MAX_MS = 10 * 60_000
export function heartbeatFresh(dir, now = Date.now()) {
  try { return now - statSync(join(dir, ".watcher-alive")).mtimeMs <= HEARTBEAT_MAX_MS } catch { return false }
}
function handoffDir(ev) { return join(projectDir(ev), ".set", "handoff") }

function context(ev) {
  const dir = handoffDir(ev)
  const s8 = session8(ev.session_id)
  // the tail only: every PostToolUse runs this, and a whole read of a 300 MB transcript cost 2 s and 1.5 GB
  const lines = ev.transcript_path ? tailLines(ev.transcript_path) ?? [] : []
  const tok = readTokens({ tokensFiles: [join(dir, `.context-tokens-${s8}`)], transcriptPath: ev.transcript_path })
  const markerPath = join(dir, `.written-${s8}`)
  let markerAgeMs = null
  try { markerAgeMs = Date.now() - statSync(markerPath).mtimeMs } catch { /* not armed */ }
  // Watched: the per-repo watcher file exists, or a watcher run from the package (no copy) wrote its
  // heartbeat within the last 10 min.
  const autoClear = existsSync(join(projectDir(ev), ".claude", "hooks", "watch-auto-clear.sh")) || heartbeatFresh(dir)
  const killed = existsSync(join(dir, ".no-keepgoing")) ? ".no-keepgoing"
    : existsSync(join(dir, `.no-keepgoing-${s8}`)) ? `.no-keepgoing-${s8}` : null
  const markerFresh = markerAgeMs == null ? false : markerFreshness({ dir, s8, transcriptPath: ev.transcript_path }).fresh
  // Surfacing (change started-after-self-exclusion): the watcher announces a start-filter skip in
  // .excluded-<session8> — line 1 carries the resume command; this hook is where the session
  // finally hears it (D1: never typed keys — an excluded session's hooks are exactly the stale ones).
  const excludedPath = join(dir, `.excluded-${s8}`)
  let excludedResume = `claude --resume ${ev.session_id}`
  try {
    const cmd = readFileSync(excludedPath, "utf8").split("\n")[0].trim().replace(/^\S+\s+/, "")
    if (cmd.startsWith("claude ")) excludedResume = cmd
  } catch { /* not excluded */ }
  const excluded = existsSync(excludedPath) ? excludedPath : null
  return { dir, s8, lines, tokens: tok.tokens, markerAgeMs, markerFresh, killed, autoClear, excluded, excludedResume, statePath: join(dir, `.keepgoing-${s8}.json`) }
}

function log(dir, line) {
  try { mkdirSync(dir, { recursive: true }); appendFileSync(join(dir, "keep-going.log"), `${new Date().toISOString()} ${line}\n`) } catch { /* not the critical path */ }
}

async function main(argv) {
  const [mode, ...rest] = argv
  const opts = parseArgs(rest)
  let input = ""
  for await (const chunk of process.stdin) input += chunk
  let ev
  try { ev = JSON.parse(input) } catch { return 0 } // a hook error must never break the work
  if (!ev?.session_id) return 0
  // Headless runs are left alone unless --headless: a script's `claude -p` inside the project must
  // not be pushed through 40 extra turns. Measured 2026-09-21 on 2.1.278: hooks of an interactive
  // session see CLAUDE_CODE_ENTRYPOINT=cli, hooks of a `claude -p` run see sdk-cli. Absent ⇒ run.
  // Checked BEFORE the transcript is read: a headless run reads nothing.
  const entry = process.env.CLAUDE_CODE_ENTRYPOINT
  if (entry && entry !== "cli" && !opts.headless) {
    if (mode === "stop") log(handoffDir(ev), `allow ${session8(ev.session_id)}  headless run (entrypoint ${entry}) — pass --headless to keep it going too`)
    return 0
  }
  const c = context(ev)

  if (mode === "post") {
    // The exclusion notice FIRST, whatever the context size: the watcher will never act on this
    // session, so the threshold advice below would be advice nobody acts on either. Said once —
    // the state file. (A new human prompt resets decideStop's state and may say it once more;
    // that is a human coming back to a still-excluded session, not spam.)
    if (c.excluded) {
      const st = readState(c.statePath)
      if (!st.excludedSaid) {
        st.excludedSaid = true
        try { mkdirSync(c.dir, { recursive: true }); writeFileSync(c.statePath, JSON.stringify(st)) } catch { /* said again next call, harmless */ }
        log(c.dir, `post  ${c.s8}  excluded by --started-after — surfaced once (${c.excludedResume})`)
        process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: "PostToolUse",
          additionalContext: `[auto-clear] THIS session is excluded by the watcher's --started-after: it started before the clear-reload wiring, so a /clear here would reload nothing — no automatic clear and no handoff nudge will reach it. To be covered, exit and run: ${c.excludedResume} (same session id, new process, current hooks). Reason on file: ${c.excluded}.` } }) + "\n")
      }
      return 0
    }
    // An early warning inside a long turn: the Stop check only runs at the END of a turn.
    const o = { ...DEFAULTS, ...opts }
    if (!c.autoClear || c.killed || c.tokens == null || c.tokens < o.threshold) return 0
    if (c.markerFresh ?? (c.markerAgeMs != null && c.markerAgeMs <= o.markerFreshMs)) return 0
    const st = readState(c.statePath)
    if (st.postAt && Date.now() - st.postAt < o.postEveryMs) return 0
    st.postAt = Date.now()
    try { mkdirSync(c.dir, { recursive: true }); writeFileSync(c.statePath, JSON.stringify(st)) } catch { /* next call warns again */ }
    log(c.dir, `post  ${c.s8}  context ${c.tokens} ≥ ${o.threshold} — asked for a handoff`)
    process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: "PostToolUse",
      additionalContext: `[keep-going] Context is at ${c.tokens} tokens (limit ${o.threshold}). Finish the step you are on, then write the handoff (/handoff, Write or Edit tool — never Bash) and end your turn; the auto-clear watcher continues you from it.` } }) + "\n")
    return 0
  }

  if (mode !== "stop") return 0
  const message = ev.last_assistant_message ?? lastAssistantText(c.lines)
  // An excluded session never gets a clear: the watcher skips it by the start filter, so "the
  // handoff is armed — waiting for the auto-clear" would wait for ever. The exclusion acts like
  // no watcher here (the post hook already early-returns on it).
  const d = decideStop({
    message, backgroundTasks: Array.isArray(ev.background_tasks) ? ev.background_tasks : [],
    tokens: c.tokens, markerAgeMs: c.markerAgeMs, markerFresh: c.markerFresh, killed: c.killed, human: lastHumanPrompt(c.lines),
    state: readState(c.statePath), opts, autoClear: !c.excluded && c.autoClear,
  })
  if (d.block) {
    // The budget lives in the state file. If it cannot be written, every Stop starts at 1/40 again,
    // and the nudge never runs out: measured 60 blocks out of 60 stops in a consumer review
    // (2026-11-08, H1). A budget that cannot be kept must not be spent, so the stop goes through.
    try { mkdirSync(c.dir, { recursive: true }); writeFileSync(c.statePath, JSON.stringify(d.state)) } catch (e) {
      log(c.dir, `allow ${c.s8}  the budget state cannot be written (${e.code || e.message}) — letting the stop through`)
      return 0
    }
  } else {
    try { mkdirSync(c.dir, { recursive: true }); writeFileSync(c.statePath, JSON.stringify(d.state)) } catch { /* nothing spent */ }
  }
  log(c.dir, `${d.block ? "block" : "allow"} ${c.s8}  ${d.why}`)
  if (d.block) process.stdout.write(JSON.stringify({ decision: "block", reason: d.reason }) + "\n")
  return 0
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(await main(process.argv.slice(2)))
}
