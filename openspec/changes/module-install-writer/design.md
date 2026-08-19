## Context

`lib/set_orch/module_install.py` reads and never writes. `InstallReport` — a dataclass documented
as "never silent, in either direction" — is not constructed anywhere in the repository, and no
function places a module's declared files into a project. The reading half is live: the fleet
screen consults it to report a capability as *not connected*, which is an invitation nothing can
accept.

The framework already writes into projects, through `set-project init` → `profile_deploy`. That
path carries the 2026-07-19 safety track in full: a hash ledger (`set/.deploy-manifest.json`),
`protected` files skipped when the project edited them, `once: true` for files seeded and never
rewritten, committed deletions read as intent, tombstones, and ownership checks. Every one of
those exists because a specific silent overwrite reached a real repository.

So the question this design answers is not "how do we copy files". It is **which of the two
existing halves the writer belongs to**, and what to do about the fact that they already parse the
same manifest twice.

**Measured while writing this design, on this repository:**

| what | measurement |
|---|---|
| `InstallReport` constructed anywhere | **0 sites** — the type exists, nothing produces one |
| Manifests in the repo | 3 (`example/starter`, `mobile/capacitor-nextjs`, `web/nextjs`) |
| Do the two parsers agree on those? | **yes: 3/3, 4/4, 50/50 paths identical** |
| Manifests declaring `executable:` | **0** |
| `profile_deploy` mentions of `executable` | **0** — the deploy path does not know the concept |

The last two rows are the finding. The declaration parser (`plan_files`) excludes a module's
executable part; the deploy parser has never heard of it. They agree today **only because no
manifest exercises the difference**, which is the weakest possible reason for two things to agree.

## Goals / Non-Goals

**Goals:**
- One function that performs an install and returns the report the module already defines.
- Reuse of the per-file safety discipline, not a copy of it.
- A refusal — before the first byte — when a declared requirement is missing.
- A spec for this capability, covering the half that shipped without one as well as the new half.

**Non-Goals:**
- Any screen, route or button. `fleet-view` 6.5/7.15/9.17 consume this; they do not define it.
- Uninstall, downgrade, or repair of a diverged file.
- Changing what `set-project init` does. This design **names** a divergence in it and proposes the
  narrowest correction; it does not rework the deploy engine.
- Installing a module's code. A module is installed on the machine by a package manager; only its
  declared project files are ever written.

## Decisions

### D1 — The writer plans with the DECLARATION and writes with the DEPLOY ENGINE

The plan (which paths) comes from `plan_files(decl)`; the write (each path, with the ledger and the
flags) goes through the deploy engine's existing per-file path.

*Alternatives considered.* **(a) A new copier inside `module_install`.** Rejected: it would have to
re-implement the ledger, `protected`, `once`, deletion-intent and tombstones, and it would be a
second place to fix each of them. The framework's own rule names this as the failure mode — a
parallel mechanism built because ours would be tidier. **(b) Call `_deploy_single_template`
wholesale and let it derive the file list.** Rejected on the measurement above: that path does not
know `executable`, so a module that declares one would have its code copied into the project. The
exclusion has to be structural, and the only way to make it structural is for the excluding parser
to produce the list that reaches the writer.

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

### D3 — The install record is written last, and only on a run that wrote something

`InstallRecord.save()` exists and is called nowhere. It is written after the last file, never
before and never on refusal.

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
