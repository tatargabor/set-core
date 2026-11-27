## Context

The relay already makes a permission prompt answerable from the channel: a `PermissionRequest`
hook (`set-hook-permission-relay`) posts Allow / Deny and waits, and the terminal stays live.
When a PreToolUse hook raised the prompt with `ask`, the reason it gave is drawn only in the
terminal. The runtime passes the `PermissionRequest` hook `tool_name`, `tool_input` and
`permission_suggestions`, and nothing from the asking hook (measured 2026-11-22, B-188). The
transcript does not carry hook output either. So the relay cannot recover the reason by itself:
the asking hook has to hand it over.

`set-hook-notify-relay --text` already exists for a hook's own reason, but it sends a
SEPARATE one-way notification, so the reason and the Allow / Deny land in two unrelated
messages. The owner wants to decide in one place.

## Goals / Non-Goals

**Goals:**
- The Allow / Deny post itself carries the asking hook's reason and enough of the command to judge it.
- Generic: any hook that returns `ask` can use the carrier; nothing in set-core names a particular guard.
- Safe by construction: a reason can only ever be shown for the exact call it was written for.

**Non-Goals:**
- Automatic answers to permissions.
- Changing the asking hooks; their owners adopt the carrier.
- Recovering a reason from a hook that does not call the carrier.

## Decisions

**D1 — A shared store keyed by (session, hash of tool + canonical input), not by tool_use_id.**
The two hooks run separately and share no process. The `PermissionRequest` payload carries no
`tool_use_id` that is known to match the PreToolUse one, but both payloads carry the same
`session_id`, `tool_name` and `tool_input`. Key: `sha256(tool_name + "\0" + json.dumps(tool_input,
sort_keys=True, separators=(",", ":")))[:24]`, in a file named `<session8>-<key>.json` under
`<relay state>/ask-reasons/`. Alternative considered: the most recent reason of the session.
Rejected, because a hook that asks and is then superseded by another call would put its reason
on the wrong prompt. Exact input equality makes a mismatch impossible, and the fail direction of
an unmatched reason is "no reason shown", which is today's behaviour.

**D2 — The carrier is a mode of `set-hook-notify-relay`, not a new binary.** That carrier is
already the one that takes a hook's own text (`--text`), is on PATH through `install.sh`, and has
the same "never block, exit 0, log no content" contract. A guard has one name to call.

**D3 — Freshness 600 s, single use, prune on touch.** A guard's `ask` and the relay's post are
seconds apart. Ten minutes covers a slow machine and still bounds how long text sits on disk.
Consuming on read means a repeated identical command that asks again needs a fresh reason,
which the guard writes again anyway. No daemon: pruning happens when the store is written or
read.

**D4 — Command bound 1200 characters, reason 600, explicit cut marker.** A chat message is
limited (Discord: 2000 characters), and the post also carries the header and the options line.
The 160-character summary measured on 2026-11-27 stopped before the part the guard objected to.
The marker (`… [+N chars cut]`) makes a cut visible instead of silent.

**D5 — The store holds the reason only while the switch is on.** With the relay off nothing reads
it, so nothing is written (the same "off is the common case, answer it first" rule the carrier
follows today).

## Risks / Trade-offs

- [A guard's reason quotes part of the command, so content goes to the channel] → It goes exactly
  where the command summary already goes, through the same outbound, and the outbound's own
  masking applies. Nothing new is logged locally.
- [Canonical JSON differs between the two payloads, for example in key order or float formatting]
  → `sort_keys` handles order. Any residual mismatch fails toward "no reason shown". The unit
  tests use the real payload shapes, and the live acceptance measures a real guard.
- [The asking hook never adopts the carrier] → The longer command still helps every permission
  post. The register keeps B-188 (a) open until a real guard shows its reason.

## Migration Plan

Additive. Ship the carrier mode and the post change together, then announce the stdin shape on
the bus to the family plugin's owner. Rollback means reverting the commit; stored reasons expire
by themselves within 600 s.

## Open Questions

None blocking. Whether the PermissionRequest payload of a future runtime carries the asking
hook's reason directly is worth re-measuring at the live acceptance: if it does, the carrier
becomes a fallback.
