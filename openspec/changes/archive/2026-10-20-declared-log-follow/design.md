## Context

The status contract answers questions. Each answer is one JSON envelope produced by one subprocess
run, capped at 8 MB, timed out at 30s, and cached for 30s. That shape is right for a summary and
wrong for a file that grows while you watch it.

What exists today, measured on a live producer (2026-08-02):

- An answer already carries a **relative path** to the file the work writes, inside its own tree.
- The file is **alive and growing** while being watched — a few hundred bytes in a few seconds.
- It is **line-oriented JSON**: one object per line, whose keys are the producer's own.
- set-core and the project sit on **the same machine**; the dashboard already serves HTTP.

The framework must stay domain-free. It may not know that a field called `log` means a log — the
next project will call it `trace`, `logFile`, or nothing at all, and a framework that recognises one
project's word has adopted that project's domain.

## Goals / Non-Goals

**Goals:**
- A project can point at a file it wants watched, using the vocabulary the contract already has.
- The surface can follow that file live, with no polling loop written by hand and no restart.
- The path a client may follow is decided by the project's own answer, not by the client.
- Nothing read this way is persisted anywhere by set-core.

**Non-Goals:**
- Searching, filtering or parsing the file's contents. The panel shows lines; it does not
  understand them.
- Writing to the file, rotating it, or acting on what it contains.
- Following anything on another machine. Same-machine is the premise; a remote producer needs a
  different transport and is out of scope.
- Replacing the existing orchestration log panel, which reads set-core's own logs and has nothing to
  do with the contract.

## Decisions

### D1 — The declaration is an envelope key of bare field names, not a path expression

`follow: ["log"]` — the same shape as `caveats`' keys: a bare field name, matched at any depth by
walking the data. Alternatives considered:

- **A dotted path (`"running.log"`)** — rejected on measurement. `caveats` already matches bare
  names at any depth, and a dotted key there matches *nothing* and renders silently as no caveat.
  Introducing a second, differently-shaped key selector in the same envelope is how a producer ends
  up guessing which rule applies to which key. One selector rule for the whole envelope.
- **A manifest entry (`followable: [...]`)** — rejected because the manifest describes the
  *interface*, while whether a given answer has a live file is a property of the *answer*. A run
  that has finished carries no path; the declaration must be able to travel with the data.
- **Recognising a field named `log`** — rejected outright; it is the domain-in-the-framework failure
  this whole layer exists to prevent (`project-status-surface`: "The renderer recognises no domain
  field name").

### D2 — The gate is the live answer, not a path allowlist

Before streaming, the endpoint asks the project the command again and checks that the requested path
is **currently the value of a follow-declared field**. Only then does it open the file.

The alternative — "any path inside the project tree" — is cheaper and wrong in the expensive
direction: it turns a status endpoint into a general file reader for the whole tree, and the check
that would have stopped it lives in the caller. *The guard belongs where the effect is.* Asking the
project costs one subprocess run, measured at roughly a tenth of a second, which is nothing against a
stream that stays open for minutes.

Symlink resolution is part of the same gate, not a separate courtesy: the path is resolved with
`realpath` and must still be inside the project root afterwards. A declared path is data from
outside; a symlink is exactly how "inside the tree" stops being true without the string changing.

### D3 — Server-sent events, not MCP and not a websocket

SSE is one-way, text, line-oriented and reconnects on its own — the exact shape of the problem.

- **MCP** was the user's own suggestion to *avoid*, and the reason is worth writing down: an MCP call
  is request/response, so a growing file has to be chunked into calls, and every chunk travels
  through a model's context. The browser and the server are on the same machine; the model has no
  business in the path.
- **A websocket** would work and costs a protocol upgrade, a heartbeat and a reconnect policy for a
  stream that never needs to send anything upward.

### D4 — The panel renders lines, and recognises nothing inside them

A line that parses as JSON is shown as compact `key: value` pairs in its own key order; a line that
does not is shown as text. No key is promoted, coloured, or given a special place — that would be
D1's mistake one layer down, and JSONL conventions differ per producer.

### D5 — Bounded by construction, because an unbounded stream is a denial of service you built

The stream carries a line budget and a rate cap, and it starts from the **end** of the file rather
than replaying history. Following is about *now*; replaying a file that has grown to hundreds of kilobytes
would push the interesting line off the screen before anyone reads it.

## Risks / Trade-offs

- **A log line contains the project's domain in its rawest form** (records, names, quoted business
  rules) → It is shown and dropped. Nothing is cached, nothing is logged; the endpoint's own logging
  records byte counts and error classes, never content — the rule `project_status.py` already
  follows.
- **The gate re-runs a command on every follow request** → measured at ~0.1s, and it happens once
  per stream rather than per line. If a producer's command is slow, its own `timeouts` declaration
  already covers it.
- **A file that rotates or is deleted mid-follow** → the stream ends with a stated reason rather than
  hanging. Silence must never be the report; a dead follow and a quiet file look identical otherwise.
- **A project declares a field that sometimes holds a path and sometimes null** → that is the normal
  case (nothing is running), and it means "no control offered", not an error.

## Migration Plan

Purely additive. A project that declares no `follow` key behaves exactly as today, which is every
project at the moment of writing. There is nothing to roll back beyond not declaring the key.

## Open Questions

- Whether a producer will want more than one followable field in one answer. The shape allows it (a
  list), and the surface offers one control per declared field found in the data; no evidence yet
  that anyone needs two at once.
