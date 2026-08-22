# The owner restart — written BEFORE it, because it ends the session writing it

The user approved restarting `set-agent-owner` on 2026-08-22 so the rename can be used.
That restart **ends every agent the owner holds — nine of them, including the session that
wrote this file**. Conversations survive; processes do not. So the remaining work is written
down here rather than carried in a context that is about to stop existing.

## Why the restart is needed at all

The rename shipped in `c5021d8d`. The owner service has been running since 22:14 on
2026-08-21 and holds the code it started with — measured through the screen, which answered
`unknown method 'rename'; this owner answers attach, detach, health, list, orphans, recover,
resize, start, stop, tail, write`. A service does not reload; that is the whole point of it
being the thing that holds the terminals.

## What to do after the restart, in order

1. **Check the owner is up and holds nothing.**

       systemctl --user status set-agent-owner --no-pager | head -5
       curl -s localhost:7400/api/fleet/owner

2. **Restore set-core.** From the screen (the restore control on the project header) or:

       curl -s -X POST localhost:7400/api/fleet/roster/set-core/restore | head -40

   Expect every entry to come back with `name_source: "restored"` and its recorded label —
   `set-core-34`, `set-core-bb`, `set-core-e2`, `set-core-42`, `set-core-4f`, `set-core-5c`,
   `set-core-33`. **That is the first live proof that B-45 is actually fixed**, and it is
   worth reading rather than assuming: before this change the same act gave back a
   runtime-derived name.

   Entries whose transcript is gone are `skipped`, not failed. Two of the recorded 17 are
   `no-session:` keys with no label — they are not resumable and never were.

3. **Rename them to the names their user gave them.** The pencil beside the name on each
   tile, or:

       curl -s -X POST localhost:7400/api/fleet/agents/set-core-34/rename \
            -H 'Content-Type: application/json' -d '{"new_label":"set-core-bugfix"}'

   The mapping is a HUMAN act — the framework cannot know which conversation somebody called
   `bugfix`. What the transcripts' last requests suggest, offered to the user and awaiting
   two answers:

   | current | last request in it | proposed |
   |---|---|---|
   | `set-core-33` | "PM mode ON: váltott magától…" | `set-core-pm` |
   | `set-core-4f` | "akkor most újraindítom a gépet és megnézzük" | `set-core-restart` |
   | `set-core-42` | `sac`; its declared focus is serving the other project's questions | `set-core-wpc` |
   | `set-core-5c` | a discussion of an alternative agent harness | `set-core-beszelgetes` |
   | `set-core-bb` | "PM mode behozott egy agentet ami felett nincs kontrollunk, excludeold" | `set-core-fleet` |
   | `set-core-34` | "újraalapozzuk / tisztább utat csinálj" | **unanswered** |
   | `set-core-e2` | "átgondoljuk a change-et? / apply" | **unanswered** |

   The full list of names that existed before the reboot, from the owner's journal:
   `set-core-restart`, `set-core-bugfix`, `set-core-wpc`, `set-core-fleet`, `set-core-pm`,
   `set-core-beszelgetes`, `set-core-compare`.

4. **Then close the four open tasks**, and only with what was actually seen:

   - **6.6** — LOOK at a rename in the browser: the terminal keeps its history, the tab strip
     renames, nothing restarts. Two defects were already found this way and fixed
     (`ec614fcb`); this is the act that was refused by the old owner.
   - **AC-9 / B-47** — dock an agent, rename it, and watch the panel follow. The dock
     currently in `fleet-layout.json` names `set-core-bugfix`, a label lost before any of
     this existed: it will start working the moment an agent carries that name again.
   - **AC-20** — a docked agent lost to a reboot and restored comes back into its panel. Step
     2 above is half of it; the other half needs a dock that names a live agent.
   - **7.2** — the renames themselves.

5. **`/opsx:verify` then `/opsx:archive`** once those are closed.

## Two things NOT to do

- **Do not mark 6.6, AC-9, AC-20 or B-47 done from the unit tests.** They are covered by
  tests and by mutation, and that is exactly the gap this repo keeps paying for: those checks
  ask whether the mechanism ran, and the open question is what the screen does.
- **Do not push before B-49 is scrubbed.** A committed runtime roster carrying consumer
  project names is still in local history. `set-leakscan` blocks the push, which is the
  reason it is a defect and not an incident — do not reach past it.

## The state that is already proven, so nobody re-derives it

`openspec/changes/fleet-agent-identity/measurements.md`, M1–M6. Short version: the record
stores the framework's label (verified on the live file), the screen shows one identity per
agent (verified on the live endpoint), no test regression against a baseline worktree, and
the one regression this change did introduce — 11 tests in two untouched files — was found by
that baseline diff and fixed in `be645fc9`.
