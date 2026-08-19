## Context

⚠ **Corrected 2026-08-19, hours after this file was written.** The first version opened with
*"`module_install.py` reads and never writes"*, and the proposal said no function places a module's
files into a project. **Both were wrong, and wrong in the direction that would have built a second
installer.** `profile_deploy._deploy_single_template` already copies every declared file, records
each in the ledger, and runs the announcement. The mistake was to measure the absent *product*
(`InstallReport`, genuinely never constructed outside tests) and conclude an absent *act*.

The correction is kept in place rather than swapped in, for the reason this repository keeps
finding: the corrected sentence is the cheap half, the refuted shape is the durable one. It also
changes what gets built — from *a writer* to *a guard and a report around a write that exists*.

What is actually missing, measured:

| | |
|---|---|
| `InstallReport` constructed in `lib/` | **0** — only tests build one, by hand |
| What the write returns instead | `List[str]` of human prose |
| `check_requirements` called in `lib/` | **0** — a missing requirement does not refuse anything |
| `plan_files` called in `lib/` | **0** — the executable exclusion never reaches the writer |
| Install record written | only inside the `if decl.announce is not None` branch |

So the act happens and every *account* of it is missing: no structured report, no refusal, and no
record unless the module happens to announce itself. The fleet screen's measurement — **0 ledgered
files and no declaration across three real projects** — is what that looks like from outside.

The framework already writes into projects, through `set-project init` → `profile_deploy`. That
path carries the 2026-07-19 safety track in full: a hash ledger (`set/.deploy-manifest.json`),
`protected` files skipped when the project edited them, `once: true` for files seeded and never
rewritten, committed deletions read as intent, tombstones, and ownership checks. Every one of
those exists because a specific silent overwrite reached a real repository.

So the question is not "how do we copy files" — that is answered and guarded. It is **what has to
surround that copy before a screen may offer it**, and what to do about a second finding that came
out of the same measurement.

**The second finding — two parsers of one manifest, agreeing by luck:**

| what | measurement |
|---|---|
| Manifests in the repo | 3 (`example/starter`, `mobile/capacitor-nextjs`, `web/nextjs`) |
| Do the two parsers agree on those? | **yes: 3/3, 4/4, 50/50 paths identical** |
| Manifests declaring `executable:` | **0** |
| `profile_deploy` mentions of `executable` | **0** — the deploy path does not know the concept |

The declaration parser (`plan_files`) excludes a module's executable part; the deploy parser has
never heard of it. They agree today **only because no manifest exercises the difference**, which is
the weakest possible reason for two things to agree — and the difference is a module's own code
being copied into a project, where nothing upgrades it and nothing can report its version.

## Goals / Non-Goals

**Goals:**
- One entry point that installs a module and returns the structured report the module already
  defines — instead of the prose the write emits today.
- A refusal — before the first byte — when a declared requirement is missing. Nothing refuses now.
- A record of every successful install, not only of one that happens to announce itself.
- Reuse of the per-file safety discipline, not a copy of it.
- A spec for this capability, covering the half that shipped without one as well as the new half.

**Non-Goals:**
- Any screen, route or button. `fleet-view` 6.5/7.15/9.17 consume this; they do not define it.
- Uninstall, downgrade, or repair of a diverged file.
- Changing what `set-project init` does. This design **names** a divergence in it and proposes the
  narrowest correction; it does not rework the deploy engine.
- Installing a module's code. A module is installed on the machine by a package manager; only its
  declared project files are ever written.

## Decisions

### D1 — Guard and report AROUND the existing write, never a second copier

`install_module` is a wrapper, not a writer. It checks requirements, plans with `plan_files(decl)`
so the executable exclusion is structural, calls the deploy engine's own per-file path, converts
that path's outcome into an `InstallReport`, and writes the install record last.

*Alternatives considered.* **(a) A new copier inside `module_install`.** Rejected, and after the
correction above it is not merely redundant but actively harmful: the ledger, `protected`, `once`,
deletion-intent and tombstones would all have to be re-implemented against a repository the
framework does not own, and each would then have two places to be wrong. **(b) Add the report,
the refusal and the record inside `_deploy_single_template` instead.** Rejected as scope: that
function is on `set-project init`'s critical path, its return type is consumed by the CLI as prose,
and changing what it refuses changes `project-init-deploy`'s behaviour. This capability wraps it;
a later change may migrate the CLI onto the wrapper.

*The one thing that cannot be a wrapper:* the deploy path emits **prose**, and a wrapper that
parsed those strings back into structure would be a parser over model-and-human-facing text — a
defect class named in `evidence-discipline.md`. So the per-file outcome has to be available as
data. The narrowest way is for the engine's writer to report per-file outcomes structurally and
for the existing prose to be rendered *from* that, rather than the other way round. That is a task
here, and it is the only change this design makes to `profile_deploy`'s insides.

*Consequence, stated so it is not discovered later:* the two parsers still both exist. This design
does not collapse them; it makes the safer one authoritative for installs and **records the
divergence as a task** (below). Collapsing them is a change to `project-init-deploy`'s behaviour
and belongs to that capability, not to this one.

### D2 — The requirement check runs before the first write, and refuses

`check_requirements` already computes the missing set and logs an error. Nothing acts on it.

The writer raises before planning any write. *Alternative: report it in `InstallReport` as a skip
of every file.* Rejected — that is a warning wearing a report's clothes: it returns success, the
caller renders "0 written, 12 skipped", and the reader has to notice that one of the twelve reasons
is categorically different from the others. The spec says a refusal, and a refusal is a control-flow
fact, not a field.

### D3 — The install record is written for every successful install, not only for an announcing one

Measured: `record.save(target_dir)` sits inside `if manifest is not None and decl.announce is not
None`. A module with no `announce:` section installs its files and leaves **no record that it was
installed** — which is precisely why the capability report has to fall back to inferring from file
presence, and why the fleet screen measured no declaration anywhere. The record the reader wants is
one the framework never writes.

It is written after the last file, never before and never on refusal.

A record written first states that a module is installed while the write is still in progress —
and every later reader believes it, including `version_report` and the fleet screen's capability
column. The failure is silent and durable: the record outlives the failed run.

*Open sub-decision, deliberately left to implementation:* whether a run that wrote **nothing but
skipped everything** updates the record. The proposed answer is **yes**, because the files being
present-and-owned by the project is what "installed" means, and refusing to record it would make
the next run repeat the same twelve skips forever. The report still says it changed nothing.

### D4 — `dry_run` is the default posture for anything the surface calls

The deploy engine already has `dry_run`. The install function takes the same flag and the fleet
route is expected to offer a preview before a write. This is not defensive politeness: this is the
one action on that screen that writes into a repository the framework does not own, and
`set-project init --dry-run` is already the documented way to look before leaping.

### D5 — Nothing about the target project is logged beyond its shape

The confidentiality boundary is persistence, not naming. The writer logs counts and relative paths
of its own template files; it does not log the project root, the project's file contents, or any
value read out of the project. `db_safety.py` — which logs a URL's scheme and nothing else — is the
pattern.

⚠ A neighbouring reader already breaks this: `module_install.read_project_declaration` logs the
absolute declaration path at DEBUG. That is recorded as a task rather than fixed silently here,
because it is a different function with its own callers.

## Risks / Trade-offs

- **[The writer inherits a divergence it did not create.]** The deploy path ignores `executable`.
  → Mitigated by D1 (the plan comes from the excluding parser) and by a task that makes the deploy
  path honour the same exclusion, so the two agree for a reason rather than by luck. Until that
  task lands, `set-project init` and `install_module` would treat an `executable:` manifest
  differently — and **no manifest declares one**, which is why this is a risk and not a bug.

- **[Two parsers of one manifest remain.]** → Accepted for this change, named here and as a task.
  Collapsing them changes `project-init-deploy` behaviour and needs its own spec delta; doing it
  inside a change about the writer is how a scope quietly doubles.

- **[An install that writes into a project the framework does not own.]** → Not mitigated by this
  design, because it is the point. What mitigates it is the machinery being reused: ledger,
  `protected`, `once`, deletion intent, tombstones, ownership checks, and `dry_run`. The design's
  contribution is to make sure the new entry point cannot bypass any of them, which is exactly why
  D1 refuses a copier.

- **[A report nobody renders is a report that rots.]** The unhappy paths — skip-everything,
  wrote-nothing, refused — are the ones a demo never reaches. → The consuming tasks in `fleet-view`
  (7.15, 9.17) assert what the SCREEN shows in each, not what the installer returned; the two
  differ exactly when the surface is wrong.

- **[`changed_nothing` is computed from `written` alone.]** A run that wrote nothing because it was
  given an empty plan and a run that wrote nothing because every file was skipped produce the same
  boolean. → The report already names every skip, so the two are distinguishable in the lines; the
  risk is a caller that reads only the boolean. Stated here so a renderer does not.

## Migration Plan

None. This adds a function and a spec; no existing caller changes behaviour. The install record and
the ledger are both additive on the project side, and a project that never asks for a module never
acquires either.

## Open Questions

1. **Does an install that skipped everything update the install record?** D3 proposes yes, with the
   reasoning stated. Decide at implementation, and write the answer into the spec if it differs.
2. **Should `install_module` accept a module *name* and resolve the template directory itself, or
   take a resolved `ModuleDeclaration`?** Taking the declaration keeps resolution out of the writer
   and makes it testable without a template tree; taking a name is what a route wants to call.
   Likely both, with the name form a thin resolver over the declaration form.
3. **Where does the announcement (`perform_announcement`) run in the sequence?** It edits a file the
   project owns (`CLAUDE.md` by default), so it is a write like any other and belongs inside the
   report — but it is not one of the planned files, and the report's `written` list currently means
   "a planned file". Resolve before implementing, so the announcement cannot become a silent write.
