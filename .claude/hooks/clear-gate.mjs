#!/usr/bin/env node
/**
 * clear-gate — decide whether a session may be cleared automatically. NEVER clears anything.
 *
 * ═══ THE CONTRACT (specs: auto-clear) ═══
 *
 * This script only EVALUATES. It prints one verdict per gate and exits 0 always — the exit
 * code must not become a trigger. An executor (tmux send-keys, the fleet pty owner, a remote
 * control client) reads the verdict and decides whether to type `/clear`. The package ships
 * the gate and the contract; the environment ships the keystrokes.
 *
 * Gates, all of which must hold (any failure ⇒ not eligible, and the reason is named):
 *   1. tokens     — context size ≥ threshold. Source order: the session's OWN statusline-
 *                   persisted file (`.context-tokens-<session8>`, documented
 *                   `context_window.total_input_tokens`) if fresher than the freshness bound,
 *                   else the transcript's last usage triple (works, but the transcript format
 *                   is officially unstable — this is the FALLBACK, not the source). A stale
 *                   file also falls through to the transcript — measured 2026-09-13: returning
 *                   "stale" instead starved 1061 of 1742 armed-night verdicts while the
 *                   transcripts held the true numbers. No session id ⇒ the legacy shared
 *                   `.context-tokens` (pre-9.3 shape). Unknown ⇒ not eligible: unknown must
 *                   never read as above-threshold.
 *   2. marker     — `.written-<session8>` exists in the handoff dir: per-session-id by
 *                   construction, so another session's marker can never arm THIS session
 *                   (session identity is the id, never "a handoff exists"). The session's
 *                   start (from ~/.claude/sessions/<pid>.json, earliest record wins — a fleet
 *                   restore keeps the id and restarts the process) is reported in the detail,
 *                   not enforced: blocking a restored thread from its own armed handoff was
 *                   measured harmful on 2026-09-13.
 *                   FRESH is enforced, since 2026-11-23: the session's last assistant record (else the
 *                   transcript mtime) may trail the marker by at most the request window (600 s).
 *                   A stale marker (work after the handoff) fails the gate on every path, because
 *                   a clear carries only what the handoff holds.
 *   3. idle       — transcript tail has no unanswered user message and no tool_use without its
 *                   tool_result. A tool awaiting a PERMISSION decision also has no result yet,
 *                   so a pending prompt fails this gate — which is load-bearing: a dialog
 *                   swallows the executor's keystrokes (measured 2026-09-12).
 *   4. background — OFF by default since 2026-11-23: background bash tasks, a `sac wait --once`
 *                   watch and a background subagent all survived /clear on 2.1.330, and their
 *                   notifications reached the fresh session
 *                   (docs/investigations/2026-11-23-background-survival-rerun.md). With
 *                   `backgroundWorkBlocks: true` (opt-in, fail-closed) the armed handoff must
 *                   DECLARE no background work via BACKGROUND_NONE_PATTERN; unresolvable ⇒
 *                   blocked (an unreadable declaration is not a "none"). The gate never looks
 *                   at processes — only at that declaration.
 *   Clear request — `.clear-request-<session8>` (or `.clear-request-any`, whichever session of the
 *                   tree is eligible first) in the handoff dir: JSON {"next","from","at"}. A valid
 *                   request (parses, non-empty `next`, younger than the request TTL) whose `next`
 *                   the armed handoff names as a whole token, and whose handoff was the session's
 *                   LAST act (transcript mtime ≤ marker mtime + request window, default 600s — work
 *                   done after the handoff would be lost), lets gate 1 pass BELOW the threshold — a session that has
 *                   just finished a unit of work clears at the boundary instead of carrying it into
 *                   the next one. Every other gate still holds: own marker, idle, background,
 *                   opt-out (an opt-out beats a request). The verdict's `request` names the file so
 *                   the executor can claim it (rename) before it types, and delete it after.
 *   Arm nudge   — NOT a gate: the verdict's `nudge` says whether the executor should type `/handoff`
 *                   into an idle session with no FRESH marker at ≥ nudge-ratio × threshold (default
 *                   1.0: the handoff runs right before the clear). Measured 2026-11-23 in one consumer
 *                   tree: 80 of 141 watched sessions never armed. The former 0.6 asked at 240k, and
 *                   the 400k clear lost everything done in between. Each ask is recorded first
 *                   (`.handoff-nudged-<session8>`, then `.2`, `.3`; the verdict names the next one).
 *                   A session is asked again only after it answered, and at most 3 times. Idle and
 *                   opt-out hold for it like for a clear. `--nudge-ratio 0` turns off the size ask.
 *   Warm-idle   — the SECOND trigger beside the size threshold (change warm-idle-rotation). The runtime
 *                   compacts an idle 200k+ session by itself at ~53.8 min after its last request
 *                   (documented as idle compaction; measured: ≈ 35 % of one product family's auto
 *                   compactions, every one under 250k). The verdict's `idle` {due, minutes, floor,
 *                   late, reason} is due for a session that meets all of these:
 *                   · its turn has ended;
 *                   · it is at ≥ --idle-floor tokens (default 200 000, the runtime's own floor);
 *                   · it is not opted out;
 *                   · either it has been idle for ≥ --idle-minutes (default 48) but < 54, or it
 *                     answered a warm-idle nudge (its marker is newer than the record).
 *                   A due verdict lets gate 1 pass below the threshold, like a valid request; an
 *                   unarmed session gets the arm nudge instead (same record, so it is asked once).
 *                   An armed session is due only when its handoff was its LAST act: an older marker
 *                   would clear away the work done since. Past 54 min `late` is set and nothing is
 *                   typed. The verdict's `trigger` names size | request | warm-idle.
 *   5. optout     — two kill-switch scopes: `.no-autoclear` in the handoff dir disables the
 *                   whole tree (project level); `.no-autoclear-<session8>` disables one
 *                   session. Presence blocks the clear whatever else holds — the user creates
 *                   them (or asks the agent to) and the gate obeys; an agent's verbal promise
 *                   cannot disable the watcher, a marker file can.
 *
 * Usage:
 *   node clear-gate.mjs [--session <id>] [--threshold N] [--freshness SEC]
 *        [--dir <handoffDir>] [--transcript <path>] [--tokens-file <path>] [--json] [--dry-run]
 *        [--compact-on-background true|false] [--compact-threshold N]
 *        [--request-ttl SEC] [--request-window SEC] [--nudge-ratio R]
 *        [--idle-minutes M] [--idle-floor N]
 *   The verdict's `action` is `clear` (all gates hold), `compact` (opt-in: only background work refuses
 *   the clear; the session keeps its agents) or null.
 *   A hook-style JSON on stdin (session_id, transcript_path, cwd) is also accepted.
 *
 * Exit code is 0 whenever the evaluation itself ran (eligible or not); 2 on usage/setup error.
 * `--dry-run` is accepted for executor symmetry: the gate never triggers, dry or not.
 */
import { closeSync, existsSync, openSync, readFileSync, readSync, writeFileSync, readdirSync, statSync, unlinkSync } from "node:fs"
import { basename, join, resolve } from "node:path"

const MARKER_PREFIX = ".written-"
// 400k — owner decision 2026-11-23 evening: the native window moves to 550k (a backstop, firing near
// ~500k) and our own clear sits at 400k, because 70–120k is loaded before work starts and 320k left too
// little room for planning (measured: context at the first call median 68k / p90 100k). History —
// the earlier 320k default, MEASURED 2026-11-23 from
// 543 native `compact_boundary` records (trigger auto, since 2026-11-01) on this machine's transcripts:
// with claude-opus-5-5 at autoCompactWindow 400k, the native compact fires at 366–372k (328 of 543 in
// 355–380k); the rest fire EARLIER (200–350k). The former 550k (2026-11-12) — and 500k before it — sat
// above that point: the watcher log of one consumer tree peaked at 499 825 on an unarmed verdict. 320k
// leaves ~46k under the cluster; an idle turn end at ≥ 320k preceded 53 % of those auto compacts
// (350k: 37 %). The trigger depends on the model's autoCompactWindow — a project with a different
// window passes --threshold.
export const DEFAULT_THRESHOLD = 400_000
const REQUEST_PREFIX = ".clear-request-"
// A request older than this is stale: the boundary it marked has passed.
const DEFAULT_REQUEST_TTL_SEC = 7200
// A request is honoured only when the armed handoff was the session's LAST act: the transcript may
// not have moved more than this past the marker. Work done after the handoff is not in it, and a
// clear would lose it — a peer's `-any` request must never clear a thread that kept working.
const DEFAULT_REQUEST_WINDOW_SEC = 600
const MIN_NEXT_LEN = 3
// Arm nudge: the record that a session was asked for its handoff — once per session, never again.
export const NUDGE_PREFIX = ".handoff-nudged-"
// 1.0 since 2026-11-23 (owner rule: the handoff runs right before the clear). The former 0.6 was never
// measured; it rode the threshold from 192k to 240k, and the handoff it asked for armed a clear at 400k
// that lost everything done in between.
const DEFAULT_NUDGE_RATIO = 1.0
// A stale handoff may be asked for again, only after the previous ask was answered, and at most this
// many times in a session's life. A session that ignores the ask is left to the native compaction.
export const MAX_NUDGES = 3
const DEFAULT_FRESHNESS_SEC = 300
// Compact-on-background (change compact-under-background, measured 2026-10-21): below the harness's
// own auto-compact point, so the compact happens at an idle moment with a fresh handoff, not mid-turn.
// 350k was 16k under the 2026-11-23 native cluster (366–372k); it moves with the clear threshold.
export const DEFAULT_COMPACT_THRESHOLD = 400_000
// Background work survives /clear on 2.1.330 (measured 2026-11-23) — blocking on it is opt-in.
export const DEFAULT_BACKGROUND_WORK_BLOCKS = false
const BACKGROUND_NONE_PATTERN = "none left|none running|no (?:background|running)|nem fut(?: semmi)?|nincs(?: futó)? háttér"
// Warm-idle rotation (change warm-idle-rotation, measured 2026-11-23): the runtime's own idle
// compaction (documented: `idleCompaction`, floor CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS = 200 000)
// starts at ~53.8 min after the last request and writes its record at ~54.8. A session idle for
// --idle-minutes with ≥ --idle-floor tokens is handed off and cleared before that, on a warm cache.
// Past IDLE_STOP_MINUTES nothing is typed for idle: the compaction is already under way — but ONLY
// while the runtime's idle compaction is on. With `"idleCompaction": false` in the settings nothing
// compacts at ~54 min, so that cut-off would just drop a session that slipped past the window (a
// watcher restart, a late pass) to the 400k size path; then any idle ≥ --idle-minutes is due.
export const DEFAULT_IDLE_MINUTES = 48
export const DEFAULT_IDLE_FLOOR = 200_000
export const IDLE_STOP_MINUTES = 54
// The nudge record's trigger word: a handoff written after a warm-idle nudge is cleared at once,
// not another 48 minutes later (the nudge's own turn restarts the idle clock).
export const WARM_IDLE = "warm-idle"

/**
 * Is the runtime's idle compaction on for this project? Settings scopes in rising precedence —
 * user, project, project-local, managed — and the last one that sets `idleCompaction` to a boolean
 * wins. Unset everywhere means the runtime default: on. Unreadable or unparsable files are skipped,
 * as the runtime cannot read them either. Returns {on, source} so the verdict can name the scope.
 */
export function idleCompactionSetting({ projectDir, home = process.env.HOME ?? "" } = {}) {
  const files = [
    home && join(home, ".claude", "settings.json"),
    projectDir && join(projectDir, ".claude", "settings.json"),
    projectDir && join(projectDir, ".claude", "settings.local.json"),
    "/etc/claude-code/managed-settings.json",
  ].filter(Boolean)
  let on = true, source = "default"
  for (const f of files) {
    let v
    try { v = JSON.parse(readFileSync(f, "utf8"))?.idleCompaction } catch { continue }
    if (typeof v === "boolean") { on = v; source = f }
  }
  return { on, source }
}

export function session8(sessionId) {
  return String(sessionId ?? "").replace(/[^a-zA-Z0-9]/g, "").slice(0, 8) || "ismeretlen"
}

/**
 * The marker convention, as a function so the write-time hook and the tests share one body:
 * a marker exists ONLY for a handoff that passed the content gate. A failed gate must never
 * arm a session (test: marker.test / "a failing gate must never arm").
 */
export function armMarker(handoffDir, sessionId, handoffFile, { passed = true, now = new Date() } = {}) {
  const path = join(handoffDir, MARKER_PREFIX + session8(sessionId))
  if (!passed) {
    if (existsSync(path)) { try { unlinkSync(path) } catch { /* best effort */ } }
    return { wrote: false, path, reason: "gate not passed — no marker" }
  }
  writeFileSync(path, `${now.toISOString()} ${basename(handoffFile)}\n`)
  return { wrote: true, path }
}

/**
 * Live context size: the first FRESH statusline-persisted candidate, else the transcript
 * fallback. A stale candidate is remembered ("statusline-stale" is only reported when nothing
 * else pans out) — it must not SHORT-CIRCUIT the fallback: measured 2026-09-13 in the armed
 * consumer night, a returning-early "stale" starved 1061 of 1742 verdicts while the sessions'
 * own transcripts held the true ~528k.
 */
export function readTokens({ tokensFile, tokensFiles, transcriptPath, freshnessSec = DEFAULT_FRESHNESS_SEC, now = Date.now() } = {}) {
  const candidates = tokensFiles ?? (tokensFile ? [tokensFile] : [])
  let sawStale = false
  for (const path of candidates) {
    if (!path || !existsSync(path)) continue
    try {
      const rec = JSON.parse(readFileSync(path, "utf8"))
      const ageSec = (now - Date.parse(rec.updatedAt)) / 1000
      if (Number.isFinite(rec.totalInputTokens) && ageSec <= freshnessSec) {
        return { tokens: rec.totalInputTokens, source: "statusline", ageSec }
      }
      sawStale = true
    } catch { /* a corrupt candidate falls to the next source */ }
  }
  if (transcriptPath && existsSync(transcriptPath)) {
    const t = tokensFromTranscript(transcriptPath)
    if (t != null) return { tokens: t, source: "transcript-fallback", ageSec: null }
  }
  return { tokens: null, source: sawStale ? "statusline-stale" : "unknown", ageSec: null }
}

/**
 * The transcript's last lines, read from its last `bytes` only (the first, partial line is dropped).
 * Every reader here needs only the end of the file. Reading it whole was measured in a consumer's
 * security review (2026-11-08): a 300 MB transcript cost 2 s and 1.5 GB per hook call, and a file over
 * 512 MB cannot become one string at all, so the call crashed. Unreadable ⇒ null.
 */
export const TAIL_BYTES = 4 << 20
export function tailLines(path, bytes = TAIL_BYTES) {
  let fd
  try {
    const size = statSync(path).size
    const start = Math.max(0, size - bytes)
    fd = openSync(path, "r")
    const buf = Buffer.alloc(size - start)
    readSync(fd, buf, 0, buf.length, start)
    const lines = buf.toString("utf8").trimEnd().split("\n")
    return start > 0 ? lines.slice(1) : lines
  } catch { return null } finally { if (fd != null) closeSync(fd) }
}

/** Last usage triple in the transcript — the formula context-guard has run in production. */
export function tokensFromTranscript(path) {
  try {
    const lines = tailLines(path) ?? []
    for (let i = lines.length - 1; i >= 0; i--) {
      let e; try { e = JSON.parse(lines[i]) } catch { continue }
      const u = e?.message?.usage ?? e?.usage
      if (u && (u.input_tokens != null || u.cache_read_input_tokens != null)) {
        return (u.input_tokens ?? 0) + (u.cache_creation_input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0)
      }
    }
  } catch { /* unreadable transcript ⇒ unknown */ }
  return null
}

/**
 * Session start time from the runtime's own records (~/.claude/sessions/<pid>.json).
 * Two measured bugs lived here (fixed 2026-09-13):
 * - the old filter skipped any file whose NAME contains a dot — true of every `<pid>.json` —
 *   so the marker gate's start check NEVER ran (it announced the skip and passed on presence);
 * - a fleet restore restarts the PROCESS but keeps the session id, so matching any single
 *   record is arbitrary. The session's birth is the EARLIEST start among its records: identity
 *   is the id, never the process, and a restored session must not disown its own marker.
 */
export function sessionStartAt(sessionId) {
  const dir = join(process.env.HOME ?? "", ".claude", "sessions")
  if (!existsSync(dir)) return null
  let earliest = null
  for (const f of readdirSync(dir)) {
    if (!f.endsWith(".json")) continue // skips the <pid>.<hash>.key files too
    try {
      const rec = JSON.parse(readFileSync(join(dir, f), "utf8"))
      if (rec.sessionId === sessionId && Number.isFinite(rec.startedAt)) {
        earliest = earliest == null ? rec.startedAt : Math.min(earliest, rec.startedAt)
      }
    } catch { /* a malformed record is not ours to fix */ }
  }
  return earliest
}

/**
 * The text block the runtime writes when the user interrupts a turn (Esc), with " for tool use"
 * when the interrupt answered a tool call. It is not a message to answer: the turn is over and the
 * session waits at its prompt. Read as a user message, it held the idle gate shut for ever
 * (B-252, measured 2026-11-27 on a consumer session at 421k with an armed handoff).
 */
const INTERRUPT_MARKER = /^\[Request interrupted by user( for tool use)?\]\s*$/

/** Idle: no unanswered user message, no tool_use left without its tool_result. */
export function transcriptIdle(path, window = 200) {
  if (!path || !existsSync(path)) return { idle: false, reason: "transcript missing" }
  let lines
  try {
    lines = tailLines(path)
    if (lines == null) throw new Error("unreadable")
    lines = lines.slice(-window)
  } catch { return { idle: false, reason: "transcript unreadable" } }
  const pending = new Set()
  let last = null
  for (const line of lines) {
    let e; try { e = JSON.parse(line) } catch { continue }
    const type = e.type
    if (type === "assistant" && Array.isArray(e.message?.content)) {
      for (const block of e.message.content) {
        if (block?.type === "tool_use") pending.add(block.id)
        if (block?.type === "text") last = { type: "assistant-text" }
      }
    }
    if (type === "user" && Array.isArray(e.message?.content)) {
      for (const block of e.message.content) {
        if (block?.type === "tool_result") pending.delete(block.tool_use_id)
        else if (block?.type === "text" && INTERRUPT_MARKER.test(block.text ?? "")) {
          // The interrupt ended the turn: a tool call it cut off will never get its result.
          pending.clear()
          last = { type: "interrupt" }
        } else last = { type: "user" } // an unanswered user message ⇒ mid-turn
      }
    }
  }
  if (pending.size > 0) return { idle: false, reason: `tool call(s) awaiting result: ${[...pending].length}` }
  if (last?.type === "user") return { idle: false, reason: "user message awaiting response" }
  if (last?.type === "interrupt") return { idle: true, reason: "turn interrupted by the user, nothing pending" }
  return { idle: true, reason: "turn ended, nothing pending" }
}

/**
 * When the last assistant record was written (ms), or null. This is the clock the runtime's idle
 * compaction runs on (the age of the last request), so the warm-idle trigger reads it here and not
 * from the process or the pane, which would measure the human.
 */
export function lastAssistantAt(path, window = 400) {
  if (!path || !existsSync(path)) return null
  let lines
  lines = (tailLines(path) ?? []).slice(-window)
  for (let i = lines.length - 1; i >= 0; i--) {
    let e; try { e = JSON.parse(lines[i]) } catch { continue }
    if (e?.type !== "assistant") continue
    const t = Date.parse(e.timestamp ?? "")
    if (Number.isFinite(t)) return t
  }
  return null
}

/**
 * The warm-idle verdict. It is due when ALL of these hold:
 * - the turn has ended;
 * - the context is at least the floor;
 * - the session is not opted out;
 * - one of two paths applies:
 *   · the last request is ≥ idleMinutes and < IDLE_STOP_MINUTES old (no upper bound when the
 *     runtime's idle compaction is off — runtimeCompacts false);
 *   · a warm-idle nudge was answered: the marker is newer than the nudge record.
 * Whether the marker is FRESH (the handoff was the last act) is the marker gate's business. A due
 * verdict with a stale marker is not eligible, and the nudge asks for a fresh handoff instead.
 */
export function warmIdleVerdict({ minutesOpt, floor, tokens, turnIdle, turnReason, optoutOk, lastAt, now,
  markerMtime, nudgeRecord, runtimeCompacts = true }) {
  const base = { due: false, minutes: null, floor, late: false }
  if (!(minutesOpt > 0) || !(floor > 0)) return { ...base, reason: "off" }
  const minutes = lastAt == null ? null : Math.round(((now - lastAt) / 60_000) * 10) / 10
  const out = (reason, extra = {}) => ({ ...base, minutes, reason, ...extra })
  const answered = markerMtime != null && nudgeRecord?.warm === true && markerMtime >= nudgeRecord.mtime
  if (minutes == null) return out("no timestamped assistant record")
  if (!answered && minutes < minutesOpt) return out(`idle ${minutes} min < ${minutesOpt}`)
  if (!turnIdle) return out(`turn not idle: ${turnReason}`)
  if (tokens == null) return out("context size unknown")
  if (tokens < floor) return out(`${tokens} < floor ${floor}`)
  if (!optoutOk) return out("opted out")
  if (!answered && runtimeCompacts && minutes >= IDLE_STOP_MINUTES) {
    return out(`warm window missed: idle ${minutes} min ≥ ${IDLE_STOP_MINUTES}${markerMtime == null ? " with no armed handoff" : ""} — the runtime's idle compaction is under way; nothing typed`, { late: true })
  }
  return out(answered
    ? `handoff written after the ${WARM_IDLE} nudge, ${tokens} ≥ floor ${floor}, turn ended`
    : `idle ${minutes} min ≥ ${minutesOpt}, ${tokens} ≥ floor ${floor}, turn ended`, { due: true })
}

/**
 * Is this session's marker FRESH — was its handoff the last act? One definition, shared by the gate
 * and keep-going so the two can never disagree: the last assistant record (else the transcript's
 * mtime) may trail the marker by at most windowSec. Returns {present, fresh, lagSec, markerMtime, lastAt}.
 */
export function markerFreshness({ dir, s8, transcriptPath, windowSec = DEFAULT_REQUEST_WINDOW_SEC }) {
  const markerPath = join(dir, MARKER_PREFIX + s8)
  const markerMtime = s8 && s8 !== "ismeretlen" && existsSync(markerPath) ? statSync(markerPath).mtimeMs : null
  const lastAt = lastAssistantAt(transcriptPath)
  let lastWork = lastAt
  if (lastWork == null && transcriptPath && existsSync(transcriptPath)) lastWork = statSync(transcriptPath).mtimeMs
  const lagSec = markerMtime != null && lastWork != null ? (lastWork - markerMtime) / 1000 : null
  return { present: markerMtime != null, fresh: markerMtime != null && (lagSec == null || lagSec <= windowSec), lagSec, markerMtime, lastAt }
}

/** The session's ask records, in order: `.handoff-nudged-<s8>`, then `.2`, `.3`. */
export function nudgeRecords(dir, s8) {
  const names = [NUDGE_PREFIX + s8, ...Array.from({ length: MAX_NUDGES - 1 }, (_, i) => `${NUDGE_PREFIX}${s8}.${i + 2}`)]
  const found = []
  for (const name of names) {
    const path = join(dir, name)
    if (!existsSync(path)) break
    let warm = false
    try { warm = readFileSync(path, "utf8").includes(WARM_IDLE) } catch { /* unreadable ⇒ not a warm ask */ }
    found.push({ name, mtime: statSync(path).mtimeMs, warm })
  }
  return { count: found.length, latest: found.at(-1) ?? null, next: found.length < MAX_NUDGES ? names[found.length] : null }
}

// ── CLI ──────────────────────────────────────────────────────────────────────
/**
 * The clear request for this session, if any: the session's own file first, then `-any`.
 * Returns null when none exists, else {file, path, valid, reason?, next?, from?, at?}.
 * Unparsable, `next`-less or stale ⇒ valid:false with the reason — never acted on.
 */
export function readClearRequest(dir, s8, { ttlSec = DEFAULT_REQUEST_TTL_SEC, now = Date.now() } = {}) {
  if (!s8 || s8 === "ismeretlen") return null
  for (const name of [REQUEST_PREFIX + s8, REQUEST_PREFIX + "any"]) {
    const path = join(dir, name)
    if (!existsSync(path)) continue
    let body
    try { body = JSON.parse(readFileSync(path, "utf8")) } catch { return { file: name, path, valid: false, reason: "unparsable" } }
    const next = typeof body?.next === "string" ? body.next.trim() : ""
    if (!next) return { file: name, path, valid: false, reason: "no 'next'" }
    const ageSec = (now - statSync(path).mtimeMs) / 1000
    if (ageSec > ttlSec) return { file: name, path, valid: false, reason: `stale (${Math.round(ageSec)}s > ${ttlSec}s)` }
    return { file: name, path, valid: true, next, from: typeof body.from === "string" ? body.from : "self",
      at: typeof body.at === "string" ? body.at : null }
  }
  return null
}

/** `next` as a whole token of the handoff: not glued to a letter, digit, `-` or `_` on either side. */
export function namesNext(body, next) {
  const esc = next.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  return new RegExp(`(^|[^\\p{L}\\p{N}_-])${esc}($|[^\\p{L}\\p{N}_-])`, "u").test(body)
}

// The armed handoff's body: the marker's 2nd field names the file. null when unresolvable.
function markerHandoffBody(dir, markerPath) {
  const markerContent = existsSync(markerPath) ? readFileSync(markerPath, "utf8") : ""
  const m = markerContent.match(/^\S+ (.+)$/m)
  if (!m || !existsSync(join(dir, m[1].trim()))) return null
  return { name: m[1].trim(), body: readFileSync(join(dir, m[1].trim()), "utf8") }
}

export function evaluate(opts = {}) {
  const threshold = Number(opts.threshold ?? DEFAULT_THRESHOLD)
  const freshnessSec = Number(opts.freshnessSec ?? DEFAULT_FRESHNESS_SEC)
  const dir = resolve(opts.dir ?? ".set/handoff")
  const sessionId = opts.sessionId ?? ""
  const s8 = session8(sessionId)
  // Per-session token file first (9.3: two sessions in one repo overwrote the shared file and
  // read each other's numbers). The shared name is read only when no session id exists —
  // a number from ANOTHER session's file must never arm THIS session.
  const tokensFiles = opts.tokensFile
    ? [opts.tokensFile]
    : (s8 === "ismeretlen" ? [join(dir, ".context-tokens")] : [join(dir, `.context-tokens-${s8}`)])
  const transcriptPath = opts.transcriptPath ?? null

  const gates = []
  const add = (name, ok, detail) => gates.push({ name, ok, detail })

  // 1. tokens — or a valid clear request whose `next` the armed handoff names
  const markerPathEarly = join(dir, MARKER_PREFIX + s8)
  const tok = readTokens({ tokensFiles, transcriptPath, freshnessSec })
  const over = tok.tokens != null && tok.tokens >= threshold
  const tokDetail = tok.tokens == null ? `unknown (source: ${tok.source})` : `${tok.tokens} ${over ? "≥" : "<"} ${threshold} via ${tok.source} (${Math.round(tok.ageSec ?? -1)}s old)`
  const req = readClearRequest(dir, s8, { ttlSec: Number(opts.requestTtlSec ?? DEFAULT_REQUEST_TTL_SEC) })
  let request = null, reqDetail = ""
  if (req && !req.valid) { request = { file: req.file, valid: false, reason: req.reason }; reqDetail = `; request ${req.file} refused: ${req.reason}` }
  else if (req) {
    const h = markerHandoffBody(dir, markerPathEarly)
    const windowSec = Number(opts.requestWindowSec ?? DEFAULT_REQUEST_WINDOW_SEC)
    const refuse = (reason, why) => { request = { file: req.file, valid: false, reason }; reqDetail = `; request ${req.file} refused: ${why}` }
    let afterSec = null
    if (h && transcriptPath && existsSync(transcriptPath)) afterSec = (statSync(transcriptPath).mtimeMs - statSync(markerPathEarly).mtimeMs) / 1000
    if (!h) refuse("no armed handoff", "no armed handoff for this session")
    else if (req.next.length < MIN_NEXT_LEN || !namesNext(h.body, req.next)) refuse("handoff does not name next", `handoff ${h.name} does not name next=${req.next}`)
    else if (afterSec == null) refuse("handoff freshness unknown", "transcript unreadable — cannot tell whether the session worked after its handoff")
    else if (afterSec > windowSec) refuse("handoff not the last act", `the session worked ${Math.round(afterSec)}s after its handoff (> ${windowSec}s) — that work is not in ${h.name}`)
    else { request = { file: req.file, valid: true, next: req.next, from: req.from, at: req.at }; reqDetail = `; request ${req.file} next=${req.next} from=${req.from} (handoff ${Math.round(afterSec)}s before the last transcript write)` }
  }
  // Warm-idle — the second trigger. It lets gate 1 pass below the threshold, the way a valid request
  // does. Every other gate still holds, so an unarmed session is nudged (below), never cleared.
  const now = Number(opts.now ?? Date.now())
  const turn = transcriptIdle(transcriptPath)
  const optoutEarly = !existsSync(join(dir, ".no-autoclear")) && !(s8 !== "ismeretlen" && existsSync(join(dir, `.no-autoclear-${s8}`)))
  const records = s8 !== "ismeretlen" ? nudgeRecords(dir, s8) : { count: 0, latest: null, next: null }
  // Freshness: the handoff must be the session's last act. Last work = the last assistant record's
  // timestamp, else the transcript's mtime; it may trail the marker by at most the request window.
  const windowSec = Number(opts.requestWindowSec ?? DEFAULT_REQUEST_WINDOW_SEC)
  const { fresh: markerFresh, lagSec, markerMtime, lastAt } = markerFreshness({ dir, s8, transcriptPath, windowSec })
  const warm = warmIdleVerdict({
    minutesOpt: Number(opts.idleMinutes ?? DEFAULT_IDLE_MINUTES), floor: Number(opts.idleFloor ?? DEFAULT_IDLE_FLOOR),
    tokens: tok.tokens, turnIdle: turn.idle, turnReason: turn.reason, optoutOk: optoutEarly,
    lastAt, now, markerMtime: markerFresh ? markerMtime : null, nudgeRecord: records.latest,
    runtimeCompacts: typeof opts.idleCompaction === "boolean"
      ? opts.idleCompaction
      : idleCompactionSetting({ projectDir: resolve(dir, "..", ".."), home: opts.home ?? process.env.HOME }).on,
  })
  const warmDetail = warm.due || warm.late || (warm.minutes != null && warm.minutes >= Number(opts.idleMinutes ?? DEFAULT_IDLE_MINUTES))
    ? `; ${WARM_IDLE}: ${warm.reason}` : ""
  add("tokens", over || request?.valid === true || warm.due, tokDetail + reqDetail + warmDetail)
  const trigger = over ? "size" : request?.valid === true ? "request" : warm.due ? WARM_IDLE : null

  // 2. marker — this session's own. The s8 suffix makes it per-session-id (another session's
  //    marker never matches); the start comparison stays as ANNOUNCEMENT only: measured
  //    2026-09-13, a fleet RESTORE keeps the session id and restarts the process, so the
  //    thread's own marker predates the new start — blocking on that starved the restored
  //    thread of exactly its own armed handoff.
  const markerPath = join(dir, MARKER_PREFIX + s8)
  let markerOk = false, markerDetail = "no marker for this session"
  if (s8 === "ismeretlen") markerDetail = "no session id given"
  else if (existsSync(markerPath) && !markerFresh) {
    markerDetail = `marker present but STALE: the session worked ${Math.round(lagSec / 60)} min after its handoff (> ${windowSec}s) — that work is not in it; a fresh handoff is needed`
  } else if (existsSync(markerPath)) {
    markerOk = true
    const startAt = sessionStartAt(sessionId)
    const mtime = statSync(markerPath).mtimeMs
    markerDetail = startAt == null
      ? "marker present (session record not found — start check skipped, announced)"
      : mtime >= startAt
        ? "marker present, postdates session start"
        : "marker present — predates the process start: a restored process of the SAME session id, armed from its own thread"
  }
  add("marker", markerOk, markerDetail)

  // 3. idle
  const idle = turn
  add("idle", idle.idle, idle.reason)

  // 4. background — declared none, or the profile measured its relaxation
  let bgOk = true, bgDetail = "backgroundWorkBlocks=false — background work survives /clear (measured 2026-11-23)"
  if ((opts.backgroundWorkBlocks ?? DEFAULT_BACKGROUND_WORK_BLOCKS) === true) {
    bgOk = false; bgDetail = "blocked: backgroundWorkBlocks=true (opt-in) and the handoff declares no \"none\""
    const h = markerHandoffBody(dir, markerPath)
    if (h) {
      const re = new RegExp(opts.backgroundNonePattern ?? BACKGROUND_NONE_PATTERN, "i")
      if (re.test(h.body)) { bgOk = true; bgDetail = `handoff declares no background work (${h.name})` }
      else bgDetail = `blocked: handoff ${h.name} has no resolvable "none" declaration`
    }
  }
  add("background", bgOk, bgDetail)

  // 5. optout — kill switches, two scopes: `.no-autoclear` in the handoff dir disables the
  //    whole tree; `.no-autoclear-<session8>` disables one session. Presence is the vote;
  //    the user creates them (or asks the agent to) and the gate only obeys — a verbal
  //    request to an agent binds nothing, the file does.
  const projectOff = existsSync(join(dir, ".no-autoclear"))
  const sessionOff = s8 !== "ismeretlen" && existsSync(join(dir, `.no-autoclear-${s8}`))
  add("optout", !projectOff && !sessionOff,
    projectOff ? "PROJECT opt-out present (.no-autoclear) — auto-clear disabled for this tree"
    : sessionOff ? `opt-out present (.no-autoclear-${s8}) — auto-clear disabled for this session`
    : "no opt-out")

  const eligible = gates.every((g) => g.ok)
  // action — `clear` when every gate holds; `compact` when ONLY running background work refuses the
  // clear: a /clear starts a new session and orphans the agents (their notifications and ids are
  // lost), a /compact keeps the session and so keeps them. Opt-in, and it still needs this
  // session's own marker (a fresh handoff), idle, no opt-out, and the compact threshold.
  let action = eligible ? "clear" : null
  const compactThreshold = Number(opts.compactThreshold ?? DEFAULT_COMPACT_THRESHOLD)
  if (!eligible && opts.compactOnBackground) {
    const ok = Object.fromEntries(gates.map((g) => [g.name, g.ok]))
    const tokOk = tok.tokens != null && tok.tokens >= compactThreshold
    if (tokOk && ok.marker && ok.idle && ok.optout && !ok.background) action = "compact"
  }
  // Arm nudge — due when this session has no FRESH marker (none, or a stale one), is idle, not opted
  // out, and has reached nudge-ratio × threshold (default 1.0: the ask comes at the threshold, so the
  // handoff is the last act before the clear). Each ask is recorded (base, .2, .3) before anything is
  // typed; a session is asked again only after it answered (its marker is newer than the latest
  // record), at most MAX_NUDGES times. The warm-idle trigger asks through the same records (D3).
  // `--nudge-ratio 0` turns off only the size ask, `--idle-minutes 0` only the warm-idle one.
  const nudgeRatio = Number(opts.nudgeRatio ?? DEFAULT_NUDGE_RATIO)
  let nudge = null
  if ((nudgeRatio > 0 || warm.reason !== "off") && s8 !== "ismeretlen") {
    const ok = Object.fromEntries(gates.map((g) => [g.name, g.ok]))
    const at = nudgeRatio > 0 ? Math.round(threshold * nudgeRatio) : null
    const answered = records.latest != null && markerMtime != null && markerMtime > records.latest.mtime
    const stale = markerMtime != null && !markerFresh
    const why = ok.marker ? "armed with a fresh handoff — no nudge needed"
      : !ok.optout ? "opted out"
      : records.count >= MAX_NUDGES ? `asked ${MAX_NUDGES} times and the handoff is still ${stale ? "stale" : "missing"} — left to the native compaction`
      : records.count > 0 && !answered ? `asked (${records.latest.name}) and not answered — not asking again`
      : tok.tokens == null ? "context size unknown"
      : warm.due ? null
      : warm.late ? `${WARM_IDLE}: ${warm.reason}`
      : at == null ? `size nudge off; ${WARM_IDLE}: ${warm.reason}`
      : tok.tokens < at ? `${tok.tokens} < ${at}`
      : !ok.idle ? `not idle: ${idle.reason}`
      : null
    const nudgeTrigger = why === null ? (warm.due ? WARM_IDLE : "size") : null
    const what = stale ? `stale handoff (${Math.round(lagSec / 60)} min behind)` : "unarmed"
    nudge = { due: why === null, at, tokens: tok.tokens, trigger: nudgeTrigger, record: why === null ? records.next : null,
      ask: records.count + 1, of: MAX_NUDGES,
      reason: why ?? (nudgeTrigger === WARM_IDLE ? `${what}, ${WARM_IDLE}: ${warm.reason}` : `${what} at ${tok.tokens} ≥ ${at}, idle`) }
  }
  return { eligible, action, trigger: eligible ? trigger : null, sessionId: s8, threshold, request, compactThreshold: opts.compactOnBackground ? compactThreshold : null,
    nudge, idle: warm, gates, at: new Date().toISOString() }
}

function main(argv) {
  const o = {}
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === "--json" || a === "--dry-run") o.json = a === "--json"
    else if (a === "--session") o.sessionId = argv[++i]
    else if (a === "--threshold") o.threshold = argv[++i]
    else if (a === "--freshness") o.freshnessSec = argv[++i]
    else if (a === "--dir") o.dir = argv[++i]
    else if (a === "--transcript") o.transcriptPath = argv[++i]
    else if (a === "--tokens-file") o.tokensFile = argv[++i]
    else if (a === "--background-none-pattern") o.backgroundNonePattern = argv[++i]
    else if (a === "--background-work-blocks") o.backgroundWorkBlocks = argv[++i] === "true"
    else if (a === "--compact-on-background") o.compactOnBackground = argv[++i] !== "false"
    else if (a === "--compact-threshold") o.compactThreshold = argv[++i]
    else if (a === "--request-ttl") o.requestTtlSec = argv[++i]
    else if (a === "--request-window") o.requestWindowSec = argv[++i]
    else if (a === "--nudge-ratio") o.nudgeRatio = argv[++i]
    else if (a === "--idle-minutes") o.idleMinutes = argv[++i]
    else if (a === "--idle-floor") o.idleFloor = argv[++i]
    else { console.error(`unknown flag: ${a}`); return 2 }
  }
  if (!o.sessionId || !o.transcriptPath) {
    try {
      const hook = JSON.parse(readFileSync(0, "utf8"))
      o.sessionId = o.sessionId ?? hook.session_id
      o.transcriptPath = o.transcriptPath ?? hook.transcript_path
      o.dir = o.dir ?? (hook.cwd ? join(hook.cwd, ".set/handoff") : undefined)
    } catch { /* flags only is fine */ }
  }
  const result = evaluate(o)
  if (o.json) console.log(JSON.stringify(result, null, 2))
  else {
    for (const g of result.gates) console.log(`${g.ok ? "PASS" : "FAIL"}  ${g.name.padEnd(11)} ${g.detail}`)
    console.log(`${result.eligible ? "ELIGIBLE" : "NOT ELIGIBLE"} — the gate never clears; the executor decides`)
    if (result.nudge?.due) console.log(`NUDGE due — ${result.nudge.reason}: the executor may type /handoff once`)
    if (result.trigger) console.log(`TRIGGER ${result.trigger}`)
    if (result.idle?.late) console.log(`WARM-IDLE missed — ${result.idle.reason}`)
    if (result.action === "compact") console.log(`ACTION compact — only background work refuses the clear (≥ ${result.compactThreshold})`)
  }
  return 0
}

const invoked = process.argv[1] ? resolve(process.argv[1]) : ""
if (invoked === import.meta.url.replace("file://", "")) {
  process.exit(main(process.argv.slice(2)))
}
