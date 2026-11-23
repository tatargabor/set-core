## Why

A session in a project with no agent-bus hooks wired never got the instruction to watch its
inbox as a background shell, and nothing declined its hand-written 30-minute `Monitor`. Every
expiry woke it at ~230k tokens of context for nothing. `set-doctor` had already seen the cause
and printed it as one `warn` line in a run that ended with 21 `fail` and 90 `warn`. Twenty-one of
those fails were registry entries for deleted run directories. The line also did not say that a
session was live there (B-193). Two more problems come from how the doctors are wired today.
`set-doctor` knows its module doctors only by hard-coded calls. A family doctor in another
repository reads `set-doctor` through its exit code alone, and re-implements the bus check with
its own regex. So the same fact lives in three places, and the umbrella that should see the whole
machine is not an umbrella.

## What Changes

- **A shared module-doctor contract, `doctor/1`.** It has the same record shape `set-doctor/1`
  already prints: `section`, `name`, `status`, `detail`, `fix`, `project`. Any module can speak it.
- **Modules declare themselves; nothing is hard-coded.** Each declaration is a small JSON file in
  the set-core config directory (`doctors.d/<module>.json`) and names the command, the contract it
  speaks, and the install hint. `set-doctor` runs every declared module doctor once. It merges
  their records into its own report, tagged with the module, and attaches per-project records to
  the matching registered project.
- **Two built-in adapters stay.** `sac doctor --json` (`sac.doctor/1`) and `set-kb doctor --json`
  keep working through adapters until those modules speak `doctor/1`, so no current check regresses.
- **A declared module that is not installed is reported.** This is the second-developer-machine
  case: a `warn` naming the module and the declaration's install hint, never a silent omission.
- **Recursion guard.** A module doctor run by `set-doctor` gets an environment marker. When
  `set-doctor` is started under that marker, it does not run module doctors. So a family doctor
  that calls `set-doctor` can itself be declared as a module.
- **The bus check reads what it already receives.** A project with a **live** seat that lacks the
  `session-start` or the `watch-guard` hook is a `fail` naming the seat and the missing hooks. With
  no live seat the finding stays a `warn`. A hook kind wired by more than one carrier (settings
  file and plugin both) is a `warn`.
- **Stale registry entries leave the failure count.** A registered path that no longer exists is
  reported as one aggregated `stale` record, with `set-project prune` as the fix, instead of one
  `fail` per entry. **BREAKING** for any caller that relied on a gone path setting exit 1.
- `--json` stays `set-doctor/1`. Records gain an optional `module` field, so the change is additive.

## Capabilities

### New Capabilities
- `doctor-module-contract`: the `doctor/1` record contract, the `doctors.d` declaration format and
  discovery, running each declared module doctor once, merging and attributing its records, the
  not-installed report, and the recursion guard.

### Modified Capabilities
- `machine-doctor`: the "Every registered project is checked" requirement changes. A gone path
  becomes an aggregated stale-registry record instead of a per-project `fail`. The bus check gains
  the live-seat `fail` and the duplicate-wiring `warn`. Module doctors' records reach the report
  through declarations instead of only through the hard-coded `sac` and `set-kb` calls.

## Impact

- `lib/set_doctor/checks.py`, `lib/set_doctor/cli.py`, and a new `lib/set_doctor/modules.py` for
  discovery, running, adapters and merging.
- `tests/unit/test_set_doctor.py` plus a new module-contract test file.
- `docs/reference/set-doctor.md` (contract, declarations, recursion marker).
- `install.sh` writes set-core's own declaration for `set-kb`.
- **Coordinated, not edited from this repository:**
  - The agent-bus module writes its declaration from its setup command, and later speaks
    `doctor/1`.
  - The family doctor reads `set-doctor --json` instead of its exit code, drops its duplicated bus
    regex, and declares itself.
  - Both are agreed over the agent bus. When a peer project has no live session, one is started
    through the fleet.
