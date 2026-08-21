# After the reboot — what to check, and in what order

Written 2026-08-21 22:1x, immediately before a deliberate reboot. This is the
one measurement a simulation cannot replace (see `openspec/changes/
fleet-agent-restore/measurements.md`, M1 and M7).

**Before the reboot, measured:** 26 entries across 11 projects, 26 resumable,
26 running. The roster as it stood is copied to
`openspec/changes/fleet-agent-restore/.roster-before-reboot.json`.

## 1. From a terminal, first — before trusting any screen

```bash
cd ~/code2/set-core && ./bin/set-fleet-roster verify
```

**Expected:** the same 11 projects and 26 entries, `resumable` still 26, and
**`running` 0** — nothing survives a boot. That third column going to zero while
the first two hold is the whole result.

**If `resumable` dropped:** the transcripts under `~/.claude/projects/` did not
survive as expected. That is a fact about the machine, not about this code, and
it is exactly what this check exists to find out.

**If the file is missing or truncated:** the roster did not survive an unclean
shutdown. Also a real finding — the write is atomic (`tempfile` + `os.replace`),
so this would mean the rename itself did not reach the disk.

## 2. Then the screen

```
http://localhost:7400/
```

`set-web` and `set-agent-owner` are both `enabled` with `Linger=yes`, so they
should come up without a login. The fleet screen will say *"Discovery ran: no
agent is running"* — correct, and below it a panel headed **"Agents recorded
here before"**, one row per project with its count and age, each with a Restore
control.

## 3. Restoring

One project at a time. The button states what it will actually do before it is
pressed (`Restore 6 agents`, or `Restore 4 of 7 — …`). Afterwards every entry
that did not start shows its reason.

**`set-core` holds this conversation**, session `0b7772e4-1db9-4065-a951-
0b21eeece85b`, labelled `set-core-4f`. Restoring that project brings it back —
including the thread that built this feature.

## 4. What would count as a failure

- The panel does not appear at all, while `verify` from step 1 shows entries.
- A restore reports `started` for a session that does not actually come up.
- Any entry that started silently, with no outcome line.
- A partial restore that renders as a completed one.

Delete this file once the check is done — its content belongs in
`measurements.md`, and a note that outlives its moment starts being read as
current.
