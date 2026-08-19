## Why

`lib/set_orch/module_install.py` can read everything about a module install and perform none of
it. Measured 2026-08-19: `InstallReport` — the dataclass whose whole design is "never silent, in
either direction" — **is not constructed anywhere in the repository**, and no function writes a
module's declared files into a project. The reading half is complete and in use: the fleet screen
already consults `read_project_declaration`, `read_install_record` and `version_report` to tell a
reader that a capability is *not connected*.

That is an invitation with no way to accept it. A surface that distinguishes *not connected* from
*unknown* on the stated ground that "not connected invites wiring it in" is decoration until
something can wire it in, and three tasks in the `fleet-view` change (6.5, 7.15, 9.17) are blocked
on exactly this absence.

The second reason is the one the framework rule names: this module **shipped without a
capability spec**. `openspec/specs/` has no module-install capability, so what the reading half
guarantees lives only in code, docstrings and commit messages — the failure OpenSpec was
re-adopted here to stop. Adding the writer without closing that gap would double it.

## What Changes

- **New: `install_module()`** — the writer. Takes a module declaration and a project root, writes
  the module's declared files, and returns the `InstallReport` that already exists to describe the
  run.
- **The writer reuses the existing per-file deploy discipline; it does NOT copy files itself.**
  The deploy engine already owns the hash ledger (`set/.deploy-manifest.json`), the `protected`
  and `once` flags, git-history deletion intent, and tombstones. A second copier would be a
  parallel mechanism with its own bugs against a repository the framework does not own.
- **A missing required module is a refusal, not a warning.** `check_requirements` already
  computes it; nothing acts on it. The writer raises before writing a single byte.
- **A run that changed nothing says so**, and every skipped file carries its reason. Both are
  already expressed by `InstallReport`; nothing produces one.
- **The install record is written only after a successful run**, so a refused or partial install
  cannot leave a record claiming the module is installed.
- **Retroactive: the reading half gets the spec it shipped without** — declaration, install
  record, planned files, the executable-part exclusion, and the version comparison in which
  `unknown` is never a match. Those requirements describe code that already exists and passes.
- **Not in scope**: the fleet screen's install affordance and its report rendering. Those are
  `fleet-view` 6.5, 7.15 and 9.17, and they consume this capability rather than define it.

## Capabilities

### New Capabilities
- `module-install`: what a project declares it wants, what is recorded as installed, which files a
  module places in a project, how a version mismatch is reported, and — new here — how an install
  is performed, refused, and reported.

### Modified Capabilities
<!-- None. `project-init-deploy` governs deploying a project type's templates and is unchanged:
     this capability reuses its file-writing discipline without altering what it guarantees. -->

## Impact

- `lib/set_orch/module_install.py` — gains `install_module()`; the existing readers are unchanged.
- `lib/set_orch/profile_deploy.py` — the per-file writer is called from a second entry point.
  No behaviour change; the ownership checks and the ledger already apply per file.
- `lib/set_orch/deploy_ledger.py` — read and written by the reused path, not modified.
- `openspec/specs/module-install/` — new capability spec, covering shipped behaviour as well as
  the new writer.
- Unblocks `fleet-view` 6.5, 7.15 and 9.17, which are recorded there as blocked on this absence.
- **Writes into a repository the framework does not own.** This is the same blast radius as
  `set-project init`, and it inherits that track's guards rather than restating them.
