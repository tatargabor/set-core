## Why

⚠ **This section was rewritten 2026-08-19, hours after it was written, because its central claim
was wrong.** It said *"no function writes a module's declared files into a project"*. It does:
`profile_deploy._deploy_single_template` copies every declared file, records each in the deploy
ledger, and runs the module's announcement. The original claim came from measuring
`InstallReport` — which is genuinely never constructed outside tests — and generalising from a
missing REPORT to a missing WRITE. The correction is kept here rather than swapped in silently,
because the refuted shape is the durable half: *an absent product is not an absent act*.

What is actually missing is narrower, and worse:

| | measured 2026-08-19 |
|---|---|
| `InstallReport` constructed in `lib/` | **0** — the type exists; only tests build one, by hand |
| What the write returns instead | `List[str]` of human prose (`"  Skipped (protected): …"`) |
| `check_requirements` called in `lib/` | **0** — a module whose requirement is absent installs anyway |
| `plan_files` called in `lib/` | **0** — so the executable-part exclusion never reaches the writer |
| `profile_deploy` mentions of `executable` | **0** |
| When the install record is written | **only if the module declares an `announce:` section** |

So the framework can put a module's files in a project, and cannot report what it did, refuse what
it should refuse, or record that it happened unless the module happens to announce itself. Every
one of those is a *silence*, and this repository's own rule is that a silent skip is the same class
of defect as a silent overwrite.

The consequence is already visible on a screen: the fleet surface reports capabilities as *not
connected* and measured **0 ledgered files and no declaration across three real projects** — which
is what a write that records nothing looks like from the outside. Three `fleet-view` tasks (6.5,
7.15, 9.17) are blocked on being able to offer an install and render its report; there is no report
to render.

The second reason is the framework rule's: this module **shipped without a capability spec**.
`openspec/specs/` has no module-install capability, so what the reading half guarantees lives only
in code, docstrings and commit messages — the failure OpenSpec was re-adopted here to stop.

## What Changes

- **New: `install_module()`** — a *guarded, structured* entry point over the write that already
  exists. It does not copy a byte itself: the deploy engine keeps the hash ledger
  (`set/.deploy-manifest.json`), the `protected` and `once` flags, git-history deletion intent and
  tombstones, and every one of those exists because a specific silent overwrite reached a real
  repository. What `install_module` adds is the three things missing around that write.
- **A structured report instead of prose.** The write currently returns human-readable message
  strings. A surface cannot render "which files were skipped, and why" out of sentences without
  parsing them — and a parser over prose is a defect class this repository has paid for more than
  once. `InstallReport` already models exactly this and is produced by nothing.
- **A missing required module is a refusal, not a warning.** `check_requirements` is called
  **nowhere in `lib/`** — measured. Today a module whose declared requirement is absent installs
  anyway, and the project is left in the half-installed state the check exists to prevent. The new
  entry point raises before writing a single byte.
- **A run that changed nothing says so**, and every skipped file carries its reason. Both are
  already expressed by `InstallReport`; nothing produces one.
- **The install record is written for every successful install, not only for one that announces.**
  Measured: `record.save()` sits inside the `if decl.announce is not None` branch, so a module
  with no announcement installs and leaves no trace of itself. That is why the capability report
  falls back to inferring from file presence — the declaration it would rather read is one the
  framework never writes. It stays written *after* the files, and never on refusal.
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
