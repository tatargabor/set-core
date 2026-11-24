#!/usr/bin/env node
/**
 * handoff-cost — what a handoff turn cost, and what the clear saved afterwards, from the
 * transcripts' own `usage` records (no API call, no price table).
 *
 * Units are INPUT-TOKEN EQUIVALENTS, so the answer holds across models and price changes. These
 * are the ratios that stay constant across the current price list: an uncached input token = 1,
 * a cache write = 2 (1-hour TTL) or 1.25 (5-minute TTL), a cache read = 0.1, an output token = 5.
 * Measured 2026-11-24 on one warm-idle clear: 365 823 cache-written + 1 580 656 cache-read + 5 405
 * output tokens ≈ 0.92M equivalents. 80 % of it was re-writing a cache that had gone cold, because
 * that clear ran 89 min after the last request instead of at 48.
 *
 * Usage:
 *   node handoff-cost.mjs cost <transcript.jsonl> <marker-mtime-ms> [<until-ms> [<handoff-file-name>]]
 *     → JSON {requests, input, cacheWrite, cacheRead, output, equiv, scope, since, contextBefore}
 *       The handoff turn = the assistant requests after the last user STRING entry (a human
 *       prompt, or the /handoff a nudge typed) at or before the marker, up to <until> (default
 *       now). With the handoff's file name, a turn NOT opened by /handoff (the session wrote its
 *       handoff itself) starts at its first write of that file instead: scope "self-written".
 *       contextBefore = the context size of the last request before that turn.
 *   node handoff-cost.mjs payback <fresh-transcript.jsonl> <context-before> <n>
 *     → JSON {requests, avgContext, savedEquiv} over the fresh session's first n requests, or
 *       {requests} alone while it has fewer than n. Saved = (context-before − avg fresh context)
 *       × 0.1 per request: the cache reads the old, larger context would have cost. That is the
 *       conservative side, since the old context would have kept growing.
 * Exit 0 always; unreadable input prints {"error": …}.
 */
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { fileURLToPath } from "node:url"

export const RATE = { input: 1, write1h: 2, write5m: 1.25, read: 0.1, output: 5 }

function records(text) {
  const out = []
  for (const line of String(text ?? "").split(/\r?\n/)) {
    if (!line) continue
    try { out.push(JSON.parse(line)) } catch { /* a torn line is skipped */ }
  }
  return out
}

/** One entry per API request: streaming writes the same message id several times. */
function requests(recs) {
  const seen = new Map()
  for (const r of recs) {
    if (r?.type !== "assistant" || !r.message?.usage) continue
    seen.set(r.message.id ?? `${r.timestamp}-${seen.size}`, r)
  }
  return [...seen.values()]
}

const ctxOf = (u) => (u.input_tokens || 0) + (u.cache_creation_input_tokens || 0) + (u.cache_read_input_tokens || 0)

function equivOf(u) {
  const w = u.cache_creation_input_tokens || 0
  const w1h = u.cache_creation?.ephemeral_1h_input_tokens
  const w5m = u.cache_creation?.ephemeral_5m_input_tokens
  // Split known: price each TTL; unknown: price as 1-hour, the dearer side, so a cost is never understated.
  const write = w1h != null || w5m != null ? (w1h || 0) * RATE.write1h + (w5m || 0) * RATE.write5m : w * RATE.write1h
  return (u.input_tokens || 0) * RATE.input + write + (u.cache_read_input_tokens || 0) * RATE.read + (u.output_tokens || 0) * RATE.output
}

const HANDOFF_COMMAND = /^\s*\/handoff\b|<command-name>\/handoff<\/command-name>/
const WRITE_TOOLS = new Set(["Write", "Edit", "MultiEdit"])
const SHELL_WRITE = /(^|[^0-9&])>|\btee\b|\s-i\b|\b(cp|mv)\s/

/** Does this assistant record START writing the handoff named `name` (a file write, a shell write, or the skill)? */
function writesHandoff(r, name) {
  for (const c of Array.isArray(r?.message?.content) ? r.message.content : []) {
    if (c?.type !== "tool_use") continue
    const inp = c.input ?? {}
    if (c.name === "Skill" && /(^|:)handoff$/.test(String(inp.skill ?? ""))) return true
    if (WRITE_TOOLS.has(c.name) && String(inp.file_path ?? "").endsWith(`/${name}`)) return true
    if (c.name === "Bash" && String(inp.command ?? "").includes(name) && SHELL_WRITE.test(String(inp.command))) return true
  }
  return false
}

export function handoffCost(text, markerMs, untilMs = Date.now(), handoffName = "") {
  const recs = records(text)
  let since = null
  let opener = ""
  for (const r of recs) {
    const t = Date.parse(r?.timestamp ?? "")
    if (!Number.isFinite(t) || t > markerMs) continue
    if (r.type === "user" && typeof r.message?.content === "string") { since = t; opener = r.message.content }
  }
  // A turn the /handoff command opened IS the handoff turn. Otherwise the session wrote its handoff
  // itself, often at the end of a long work turn (measured 2026-11-24: 90 work requests, 3.67M,
  // logged as one handoff): count from its first write of that file. The reading and thinking
  // before that write are left out, so a self-written cost errs low by a request or two.
  let scope = "turn"
  if (since != null && handoffName && !HANDOFF_COMMAND.test(opener)) {
    const first = recs.find((r) => {
      const t = Date.parse(r?.timestamp ?? "")
      return r?.type === "assistant" && t >= since && t <= markerMs && writesHandoff(r, handoffName)
    })
    if (first) { since = Date.parse(first.timestamp); scope = "self-written" }
  }
  const all = requests(recs)
  const inTurn = all.filter((r) => { const t = Date.parse(r.timestamp); return since != null && t >= since && t <= untilMs })
  const before = all.filter((r) => since != null && Date.parse(r.timestamp) < since).at(-1)
  const sum = { requests: inTurn.length, input: 0, cacheWrite: 0, cacheRead: 0, output: 0, equiv: 0 }
  for (const r of inTurn) {
    const u = r.message.usage
    sum.input += u.input_tokens || 0
    sum.cacheWrite += u.cache_creation_input_tokens || 0
    sum.cacheRead += u.cache_read_input_tokens || 0
    sum.output += u.output_tokens || 0
    sum.equiv += equivOf(u)
  }
  sum.equiv = Math.round(sum.equiv)
  return { ...sum, scope, since: since == null ? null : new Date(since).toISOString(), contextBefore: before ? ctxOf(before.message.usage) : null }
}

export function payback(text, contextBefore, n) {
  const all = requests(records(text))
  if (all.length < n) return { requests: all.length }
  const first = all.slice(0, n)
  const avgContext = Math.round(first.reduce((a, r) => a + ctxOf(r.message.usage), 0) / n)
  return { requests: n, avgContext, savedEquiv: Math.round(Math.max(0, contextBefore - avgContext) * RATE.read * n) }
}

const invoked = process.argv[1] ? resolve(process.argv[1]) : ""
if (invoked === fileURLToPath(import.meta.url)) {
  const [cmd, file, a, b, c] = process.argv.slice(2)
  try {
    const text = readFileSync(file, "utf8")
    if (cmd === "cost") console.log(JSON.stringify(handoffCost(text, Number(a), b ? Number(b) : Date.now(), c ?? "")))
    else if (cmd === "payback") console.log(JSON.stringify(payback(text, Number(a), Number(b))))
    else console.log(JSON.stringify({ error: `unknown command: ${cmd ?? ""}` }))
  } catch (e) {
    console.log(JSON.stringify({ error: String(e?.message ?? e) }))
  }
}
