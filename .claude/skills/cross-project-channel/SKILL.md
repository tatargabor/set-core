---
name: cross-project-channel
description: The TEMPORARY file channel between this project's session and a consumer project's session — where it lives, the append-only protocol, how to resume it after a compact or /clear, and how to check the Monitor and cron without creating duplicates. Use when coordinating with a consumer project's copilot, when resuming a session that was talking to one, or when a channel watch may have died.
---

# Cross-project agent channel

> Moved out of `CLAUDE.md` on 2026-08-22 so it loads when it is needed rather than in
> every session. Nothing was cut — the text below is the section verbatim.

## Cross-project agent channel — TEMPORARY (from 2026-07-24)

While set-core and a consumer project are being integrated, their two copilot sessions
coordinate over a **file channel**, because no shared transport exists. **Remove this
section once the real transport ships.**

*Corrected 2026-07-29 — the stated reason was wrong, and wrong in the direction that closes
off a working option.* This said `.set-control` is per-project, so `send_message`/`get_inbox`
"cannot cross a project boundary". Measured: the registry is **global**
(`~/.config/set-core/projects.json`, 38 entries), and `_find_control_worktree()`
(`mcp-server/set_mcp_server.py:462`) walks it and returns the **first** project that has a
`.set-control` directory — regardless of which project the server was started in. So both
sides would resolve to the *same* worktree; the project boundary was never the obstacle. The
real ones are that **no `.set-control` exists anywhere** (checked on both trees → both tools
return `Error: No .set-control worktree found`), and that the git-based ~15 s commit cycle is
rejected below. This is the proxy-instead-of-the-thing class applied to a code path: the
sentence described what the resolution *ought* to scope to, not what the function does.

**DECISION 2026-07-24 — do not revive the git-based control sync for this.** The existing
agent-messaging path (`set-control-sync`, `.set-control` worktree, ~15 s commit cycle) is
rejected as the cross-project channel: it caused problems in practice, and it carries
*ephemeral messages* where this coordination needs *durable state*. A live (non-git)
transport may be built later as its own piece of work; until then the file channel below is
the agreed mechanism.

**Protocol — one file, one writer.** Channel dir:
`~/.local/share/set-core/channels/<consumer-slug>/` (the slug is runtime-derived; never
hard-code a consumer name here — see External Project Confidentiality below). Each side
appends **only** to its own file and reads the other's:

| file | writer | reader |
|---|---|---|
| `set-core.md` | this project's session | the consumer's session |
| `<consumer-slug>.md` | the consumer's session | this project's session |
| `README.md` | whoever creates the channel | both |

- **Append-only**, newest last, each entry headed `## <ISO timestamp> — <TYPE>` where TYPE is
  one of `TÉNY` / `KÉRDÉS` / `VÁLASZ` / `KÉRÉS`. Answers cite what they answer (`re: …`).
- One writer per file means **no lock is needed** and no write can be lost. When a genuinely
  shared file must be edited (e.g. a planning doc in the consumer repo), take a POSIX-atomic
  lock first: `mkdir "$F.lock" || exit 1` with `trap 'rmdir "$F.lock"' EXIT`.
- Watch the other side with a Monitor on its file size — do not poll by hand.
- **A word like "measured" obliges you to show the evidence** — the command, its output, a
  `file:line`, a PID, a task id. Without one, the honest word is "assumption", and the other
  side must not write it into a rule book. This is not pedantry: a plausible guess crossed
  this bus, was reasonably taken for a measurement, and ended up in BOTH projects' rules
  before anyone ran the one-line check that disproved it. On an agent channel a confident
  claim propagates further and faster than an ordinary mistake, because the receiving side
  has every reason to trust it.
- The channel survives a reboot but **not a lost disk, and not another machine.** It is
  coordination state, not the agreement itself: anything durable belongs in a repo. Read the
  channel to rebuild the contact; read `docs/integration/consumer-integration.md` to learn
  what was decided.

**DONE 2026-07-24 — the channel moved off `/tmp` (user instruction), jointly, both sides
switched.** A restart or a power cut used to lose the status. Kept here rather than deleted,
because every reason below is a rule the *next* move would otherwise rediscover:

- **Target: `~/.local/share/set-core/channels/<slug>/`.** Measured, not invented: that root
  already exists and is the framework's durable per-user store (`memory`, `metrics`,
  `e2e-runs`, `manager`, `runtime`). Survives reboot, pollutes neither repository, and is
  symmetric — neither side's tree is the host.
- **Why not a gitignored directory inside this repo**, even though the user allowed one:
  `.gitignore` is itself a *tracked* file, so an entry naming the consumer would publish the
  name that External Project Confidentiality forbids. The gitignore would BE the leak.
  Neutral ground cannot produce that problem at all. (A generically-named local dir such as
  `docs/integration/local/` stays fine — the rule is about the consumer's name, not the
  practice.)
- **Copy, never move.** `mv` breaks the peer's live watch mid-flight; `cp` is reversible and
  leaves the old file as a fallback. Both sides append a final pointer entry to the OLD file.
  **A closed file must state its successor, not merely fall silent** — otherwise a session
  that lands on it reads the old tail as the current state, which is the exact loss the move
  was meant to prevent. The old dir also gained a `MOVED.md`; neither side deletes it.
- **The watches are the dangerous step.** Kill the old Monitor FIRST, identified by the file
  it watches (`pgrep -af "<old path>"`), and only then start one on the new path — otherwise
  two run and every entry arrives twice. Same for the cron. During the cutover **one Monitor
  watching BOTH paths** is the correct shape (used by both sides here): the duplicate bug is
  two watchers on one file, not one watcher on two.
- **`CLAUDE.md` is the second place, and the second place is itself the error source.** The
  path lives in the rule book as well as in the running watch, so a move that updates only
  the watch sends the *next* session to the dead location. The peer had seven occurrences,
  this file six — of which two were instruction-valued. Grep before declaring the move done.

**Resuming the channel after a compact, a `/clear`, or a fresh session.** The channel is the
only thing that survives — rebuild the contact from it, do not ask the user to re-explain:

1. **Find it:** `ls -dt ~/.local/share/set-core/channels/*/ 2>/dev/null | head` — the channel
   dir is the newest match. Read its `README.md` first; it carries the protocol and the
   addressing convention. (Before 2026-07-24 the channel lived under `/tmp/*-set/`; if you
   land there, its last entry names the successor.)
2. **Catch up:** read the OTHER side's file end-to-end (`<consumer-slug>.md`), then your own
   (`set-core.md`) to see what you already answered. Entries are timestamped and append-only,
   so the tail is the current state.
3. **Check both watches, then re-arm only what is missing.** A dead watch is
   indistinguishable from a quiet peer, so the work stops without anyone noticing — but
   blindly re-arming is its own bug: a duplicate fires the same catch-up twice, and two
   Monitors on one file send two notifications for every entry. **`CronList` first**, and
   look for a live Monitor process before starting one.

   **Both survive a compact** — verified on this machine, not assumed: a `persistent: true`
   Monitor started at 08:19 was still the same live PID hours later, across the compact
   that produced this session's summary (`ps -eo pid,lstart,cmd | grep <watched file>`).
   An earlier version of this section claimed the Monitor does not survive; that claim was
   a guess that travelled between two sessions and got written into both rule books before
   anyone ran the check.
   **Check the Monitor by WHAT IT IS, not by a number you remember.** Use
   `pgrep -af "<watched file>"` — match the process by the file it watches. `ps -p <pid>`
   answers a different question: whether *a* process holds that number. PIDs are recycled,
   so the answer can be yes while the Monitor is long dead, and the check then reports a
   watch that is not there. A task registry is worse still: the Monitor is a background
   process and does not appear in `TaskList` at all, so a registry lookup answers "no
   watcher" for a watcher that is running — which sends you to start a second one, which is
   the exact duplicate this step exists to prevent.

   **But `pgrep -af "<watched file>"` MATCHES ITSELF, and piping it into `grep -c` counts
   the count.** Measured four separate times on 2026-07-24: the check reported 3 and then 2
   watchers while exactly one was running. Every extra hit was the measuring command — the
   pattern appears in the searching shell's own command line, and so does any word used to
   filter it (`grep -c "while :"` matches a command containing the string `'while :'`). This
   is the same class as the completeness-word sweep: **the measurement is inside the corpus
   it measures.** Its direction is the dangerous one — it over-reports, and "two watchers"
   invites killing one, which can leave zero.

   Resolve each PID instead of counting lines, and discriminate by age — a real Monitor is
   hours old — but **the impostor is NOT always `00:00`.** Measured 2026-07-30: a self-match came
   back at `00:30`, because the measuring pipeline itself takes time to run. Age is a hint; the
   discriminator is `lstart` plus the command line, since a real watcher's argv contains the loop
   and the watched path while a self-match's contains the harness's shell snapshot.

   **And a dead watch is not necessarily a failure: check whether another session TOOK OVER.**
   Also measured that day — a Monitor exited non-zero because an incoming session had killed it by
   PID to avoid two watchers on one file, the outgoing session read that as the silent-death
   failure, re-armed, and recreated the duplicate. A deliberate kill and a spontaneous death
   produce identical evidence and need opposite responses; the channel tail separates them in one
   read.


   ```bash
   pgrep -f 'NEW=.*<watched file>' | while read -r p; do
     ps -o pid=,etime=,lstart= -p "$p"
   done          # one row per candidate; the seconds-old one is your own command
   ```

   This is the same defect class as reading a verdict out of prose: **measuring a proxy
   instead of the thing.** A remembered PID is a proxy for a process; a registry entry is a
   proxy for a running program; a matched substring is a proxy for a decision. The direction
   of the wrong answer is what makes it expensive — here it says "missing" for something
   present, and the correction is to create a duplicate.
   - a **Monitor** on the other side's file size (`persistent: true`) — how you learn about
     new entries without polling by hand. It is a real background process; `pgrep -af` on
     the watched path is the evidence, and it outlives a compact.
   - a **CronCreate** catch-up every ~10 minutes as the fallback for when the Monitor does
     die. Its prompt: read the last peer entry, check whether you have already answered it,
     do the work and reply if not, restart the Monitor if it is gone, and **say nothing at
     all when there is nothing to do** — a fallback that chatters gets muted. Pick a period
     that does not coincide with the peer's (they run one too); cron jobs are session-only
     and expire after 7 days.
4. **Announce the resume** in your own file: one `TÉNY` entry saying the context restarted and
   which entry number you have read up to, so the other side knows nothing was lost.
5. **The durable agreements are not in the channel.** The negotiated contract lives in the consumer's
   planning document (the channel's entries point at it) — read that before answering anything
   substantive, and never re-open a decision it already records.

**Addressing convention (spoken sessions).** When both copilots listen to the same
microphone, the speaker names the addressee **first in the sentence** — a turn opening with
this project's name (`set-core`, or its spoken variants) is for this session; a turn opening
with the other project's slug is not, and this session stays silent on it. An unaddressed
turn is for whoever it is actually useful to. Getting this wrong is what makes two copilots
talk over each other.
