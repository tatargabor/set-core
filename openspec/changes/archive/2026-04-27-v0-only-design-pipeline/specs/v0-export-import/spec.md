# Spec: v0 Export Import (delta)

## ADDED Requirements

**IN SCOPE:** `set-design-import` CLI for v0.app design imports into scaffolds; primary git-repo source mode (any provider, public or private); ZIP fallback mode; structure validation; manifest auto-generation; globals.css sync; manual override preservation across regenerations; clone caching.

**OUT OF SCOPE:** live API fetching from v0.app (only git/ZIP); running v0 itself (humans use v0.app web UI); editing v0 components after import; multi-source merging; framework-managed auth (delegated to system git).

### Requirement: set-design-import CLI source modes

The web module SHALL provide a `set-design-import` CLI supporting two source modes: **git** (default/primary) and **ZIP** (fallback). The two modes are mutually exclusive per invocation.

#### Scenario: Import from git repo (preferred mode)
- **WHEN** `set-design-import --git https://github.com/owner/v0-craftbrew-design.git --ref main --scaffold tests/e2e/scaffolds/craftbrew` is run
- **THEN** the CLI clones the repo (or `git fetch` + checkout if already cached) into `tests/e2e/scaffolds/craftbrew/v0-export/`
- **AND** the materialized `v0-export/` directory SHALL match the repo content at the requested ref
- **AND** the CLI exits 0 on success with a one-line summary including the resolved commit SHA

#### Scenario: Import from scaffold.yaml-declared source
- **WHEN** `set-design-import --scaffold tests/e2e/scaffolds/craftbrew` is run with no `--git` or `--source` flag
- **AND** `<scaffold>/scaffold.yaml` contains a `design_source` block with `type: v0-git` and `repo`/`ref` fields
- **THEN** the CLI uses those values as if `--git <repo> --ref <ref>` were passed
- **AND** SHALL fail with a clear error if `scaffold.yaml` lacks a `design_source` block

#### Scenario: Import from ZIP (fallback mode)
- **WHEN** `set-design-import --source craftbrew-v0.zip --scaffold tests/e2e/scaffolds/craftbrew` is run
- **THEN** the CLI extracts the ZIP into `tests/e2e/scaffolds/craftbrew/v0-export/`
- **AND** SHALL replace any existing `v0-export/` directory after explicit `--force` flag, otherwise error
- **AND** SHALL exit 0 on success with a one-line summary of files imported

#### Scenario: Conflicting source flags
- **WHEN** both `--git` and `--source` are passed
- **THEN** the CLI exits non-zero with a clear error: `"Use either --git OR --source, not both."`

#### Scenario: Source missing
- **WHEN** the `--source` path does not exist OR `git clone` of `--git` URL fails with file-not-found semantics
- **THEN** the CLI exits non-zero with a clear error message naming the missing path/URL

#### Scenario: Import without scaffold flag uses cwd
- **WHEN** `set-design-import` is run inside a scaffold directory with any source flag
- **THEN** the CLI defaults `--scaffold` to the current working directory

### Requirement: Git source mode behavior

When operating in git source mode, the CLI SHALL delegate all transport and authentication to the system `git` binary. The framework SHALL NOT implement provider-specific (GitHub/GitLab/Bitbucket) APIs or auth flows.

#### Scenario: Public repo over HTTPS
- **GIVEN** the repo is public and accessible at `https://github.com/owner/repo.git`
- **WHEN** the CLI runs `git clone` (or `git fetch` on cache hit)
- **THEN** the operation succeeds without any auth configuration

#### Scenario: Private repo via SSH
- **GIVEN** the repo URL is `git@github.com:owner-org/private-design.git`
- **AND** the user's SSH key is loaded in ssh-agent
- **WHEN** the CLI runs `git clone`
- **THEN** git uses the SSH key transparently and the operation succeeds

#### Scenario: Private repo via HTTPS with token
- **GIVEN** `GITHUB_TOKEN` env var is set to a valid PAT
- **AND** the repo URL is HTTPS
- **WHEN** the CLI runs `git clone`
- **THEN** git's credential helper picks up the token (via standard mechanisms) and the operation succeeds
- **OR** the user has configured `git config credential.helper` to read the token

#### Scenario: Auth failure produces actionable error
- **WHEN** `git clone` exits with code 128 (auth/network failure)
- **THEN** the CLI exits non-zero
- **AND** the error message SHALL name the URL that failed
- **AND** the error message SHALL list the supported auth options: SSH agent (`ssh-add -l`), `GITHUB_TOKEN` env var, configured credential helper, deploy keys
- **AND** the error message SHALL point to documentation: "See docs/design-pipeline.md § Authentication for private design repos"

#### Scenario: Provider-agnostic URL acceptance
- **WHEN** the URL is for GitLab (`https://gitlab.com/...` or `git@gitlab.com:...`), Bitbucket, self-hosted Gitea, or any standard git remote
- **THEN** the CLI treats it identically to GitHub URLs (delegates to git)
- **AND** SHALL NOT inspect the URL hostname for special handling

#### Scenario: Ref resolution
- **WHEN** `--ref` is a branch name (e.g. `main`)
- **THEN** the CLI checks out the tip of that branch at clone/fetch time
- **AND** records the resolved commit SHA in the success summary
- **WHEN** `--ref` is a tag (e.g. `v1.2.0`) or a commit SHA
- **THEN** the CLI checks out that immutable ref
- **AND** SHALL warn if the ref points to a non-tip commit on a moving branch (potential drift)

#### Scenario: Default ref
- **WHEN** no `--ref` is given AND scaffold.yaml does not specify a ref
- **THEN** the CLI defaults to `main` and emits an INFO log noting the default

### Requirement: Clone caching

The CLI SHALL cache cloned repositories under `~/.cache/set-orch/v0-clones/<sha256-of-url>/` to avoid repeated clones across invocations and across scaffolds sharing the same repo.

#### Scenario: First clone populates cache
- **GIVEN** the URL has no existing cache entry
- **WHEN** the CLI runs
- **THEN** `git clone --no-tags --filter=blob:none <URL> <cache-path>` runs (partial clone for speed)
- **AND** the requested ref is checked out
- **AND** the cache directory contains a `.set-orch-meta` file recording the URL hash and last-fetch timestamp

#### Scenario: Cache hit reuses local repo
- **GIVEN** the URL has an existing cache entry
- **WHEN** the CLI runs with the same URL
- **THEN** `git fetch --no-tags --depth=50` runs in the cache directory (refresh)
- **AND** the requested ref is checked out
- **AND** clone is NOT re-run

#### Scenario: Cache key hashes the URL
- **WHEN** computing the cache directory name
- **THEN** the URL is hashed with SHA-256 and the first 16 hex chars used as the directory name
- **AND** raw URLs (which may contain credentials) are NOT used in directory names

#### Scenario: Materialization to scaffold
- **WHEN** the requested ref is checked out in the cache
- **THEN** the cache directory contents are copied (or `cp -r --no-target-directory`) to `<scaffold>/v0-export/`
- **AND** `.git/` directory is NOT copied (scaffold's `v0-export/` is gitignored and shouldn't have its own .git)

#### Scenario: Cache pruning
- **WHEN** the cache exceeds 5 entries (5 distinct repos)
- **THEN** the LRU entry (by last-fetch timestamp) is removed
- **AND** an INFO log records the prune

### Requirement: scaffold.yaml design_source schema

`scaffold.yaml` SHALL support a top-level `design_source` block declaring the v0 source. The block is consulted by `set-design-import` (when no source flag is passed) and by the runner's deploy step.

#### Scenario: Git source declaration
- **GIVEN** scaffold.yaml contains:
  ```yaml
  design_source:
    type: v0-git
    repo: https://github.com/owner/v0-design.git
    ref: main
  ```
- **THEN** `set-design-import` (no flags) imports from that source
- **AND** the runner deploys v0-export/ from the same source

#### Scenario: ZIP source declaration
- **GIVEN** scaffold.yaml contains:
  ```yaml
  design_source:
    type: v0-zip
    path: ./local-v0-export.zip
  ```
- **THEN** `set-design-import` extracts from the relative path

#### Scenario: Missing design_source block
- **WHEN** scaffold.yaml has no `design_source` block AND `set-design-import` is run without flags
- **THEN** the CLI exits non-zero with: `"scaffold.yaml has no design_source block. Add one or pass --git/--source explicitly."`

#### Scenario: Auth credentials in URL discouraged
- **GIVEN** scaffold.yaml's `repo` field contains an embedded credential (e.g. `https://user:token@github.com/...`)
- **WHEN** the CLI parses it
- **THEN** a WARNING is logged: `"Embedded credentials in design_source.repo are not recommended; use SSH or GITHUB_TOKEN env var instead."`
- **AND** import proceeds (the user may have a legitimate reason)

### Requirement: v0 export structure validation

The importer SHALL validate that the extracted ZIP matches the expected v0 export structure before proceeding.

#### Scenario: Valid v0 export
- **GIVEN** the ZIP contains `app/` (App Router pages), `components/ui/` (shadcn primitives), `package.json`, and `app/globals.css`
- **WHEN** the importer validates the structure
- **THEN** validation passes silently and import continues

#### Scenario: Missing App Router
- **GIVEN** the ZIP has no `app/` directory
- **WHEN** validation runs
- **THEN** the importer exits non-zero with: `"v0 export missing app/ directory — was the export generated from a Next.js project?"`

#### Scenario: Missing shadcn ui primitives (HARD FAIL)
- **GIVEN** the ZIP has no `components/ui/` directory
- **AND** the scaffold targets shadcn (`scaffold.yaml` has `ui_library: shadcn`)
- **WHEN** validation runs
- **THEN** the importer EXITS non-zero with: `"v0 export missing components/ui/ but scaffold targets shadcn. The export is broken — regenerate in v0 ensuring shadcn primitives are included."`
- **AND** there is NO continue-with-warning fallback (per design D8: declared design with broken state = fail)

#### Scenario: Missing components/ui/ when scaffold does not use shadcn
- **GIVEN** the ZIP has no `components/ui/` directory
- **AND** the scaffold's `ui_library` is something other than shadcn
- **WHEN** validation runs
- **THEN** the missing directory is acceptable; importer continues

#### Scenario: Missing globals.css
- **GIVEN** the ZIP has no `app/globals.css` (or `styles/globals.css`)
- **WHEN** validation runs
- **THEN** the importer exits non-zero with: `"v0 export missing globals.css — design tokens cannot be extracted"`

### Requirement: Manifest auto-generation

The importer SHALL auto-generate `<scaffold>/docs/design-manifest.yaml` from the v0 file tree using App Router conventions and import-graph traversal. The same path convention applies after runner deployment to consumer projects: the manifest is deployed to `<project>/docs/design-manifest.yaml`. All readers (web module slice provider, fidelity gate) SHALL look for the file at `<project>/docs/design-manifest.yaml` at runtime, NOT at the scaffold path.

#### Scenario: Generate manifest from App Router tree
- **GIVEN** v0-export contains `app/page.tsx`, `app/kavek/page.tsx`, `app/kavek/[slug]/page.tsx`
- **WHEN** manifest auto-generation runs
- **THEN** the manifest contains entries for `/`, `/kavek`, `/kavek/[slug]` with their route file paths
- **AND** each entry's `component_deps` lists files transitively imported by the page
- **AND** each entry's `scope_keywords` is derived from the route segments and the first H1 in the page (lowercased, kebab-cased)

#### Scenario: Shared components captured under `shared:`
- **WHEN** manifest auto-generation runs
- **THEN** files matching `components/ui/**`, `components/header.tsx`, `components/footer.tsx`, `app/layout.tsx`, `app/globals.css` SHALL be listed under the `shared:` key
- **AND** these files are included in EVERY change's design-source slice (always copied)

#### Scenario: shared_aliases field for project rename tolerance
- **WHEN** the scaffold author hand-authors a top-level `shared_aliases:` block in `design-manifest.yaml`:
  ```yaml
  shared_aliases:
    v0-export/components/header.tsx: components/site-header.tsx
    v0-export/components/footer.tsx: components/site-footer.tsx
  ```
- **THEN** the field maps v0-export paths to the project's renamed equivalents
- **AND** the skeleton-check (in `design-fidelity-gate`) treats these as equivalent (renamed file is not a violation)
- **AND** auto-generation NEVER writes `shared_aliases:` — it is hand-authored only
- **AND** `--regenerate-manifest` PRESERVES `shared_aliases:` across regenerations (the entire block is treated as a `# manual` override)

#### Scenario: shared_aliases default empty
- **WHEN** no `shared_aliases:` block is present in the manifest
- **THEN** the field defaults to empty `{}`
- **AND** skeleton-check requires exact path equivalence (no rename tolerance)

#### Scenario: Manual override preserved across regeneration
- **GIVEN** an existing `design-manifest.yaml` has a line annotated with `# manual` comment
- **WHEN** the importer regenerates the manifest with `--regenerate-manifest`
- **THEN** lines marked `# manual` SHALL be preserved verbatim in the new file
- **AND** unmarked lines may be replaced by auto-generation

#### Scenario: --regenerate-manifest with no existing file
- **GIVEN** no `design-manifest.yaml` exists yet
- **WHEN** the importer runs with `--regenerate-manifest`
- **THEN** a fresh manifest is generated (the flag is treated as "generate, overriding any existing file" — no error)

### Requirement: Scope-keyword collision detection

The importer SHALL detect and report duplicate `scope_keywords` across multiple manifest routes during generation. Collisions cause silent multi-route slice inflation at dispatch time, which inflates context size and reduces agent focus.

#### Scenario: Duplicate keyword across routes warned
- **GIVEN** auto-generation produces routes `/winkosar` and `/penztar` both containing the keyword `cart`
- **WHEN** the manifest writer finalizes the file
- **THEN** a WARNING is emitted listing the conflicting keyword and the routes that share it
- **AND** the warning suggests either renaming one route's keyword or accepting the multi-match behavior
- **AND** the manifest is still written (warning is non-blocking)

#### Scenario: Hard failure on identical scope_keywords lists
- **GIVEN** two routes have identical `scope_keywords` lists
- **WHEN** the writer finalizes
- **THEN** the importer ERRORs (not warns) — identical lists would always select both routes for any matching scope, defeating per-route slicing
- **AND** the importer exits non-zero with the offending route paths and a remediation suggestion

### Requirement: globals.css sync to scaffold

The importer SHALL copy `v0-export/app/globals.css` (or `styles/globals.css`) to `<scaffold>/shadcn/globals.css`, replacing any existing file.

#### Scenario: globals.css synced after import
- **WHEN** the importer completes
- **THEN** `<scaffold>/shadcn/globals.css` is byte-identical to `v0-export/app/globals.css`
- **AND** if the destination existed previously, it is overwritten without prompt
- **AND** the runner that deploys scaffolds picks up the new globals.css automatically

### Requirement: v0 template quality validation

The importer SHALL run a quality validation pass after extraction/clone and BEFORE writing the manifest. Failures are reported but most are non-blocking — the scaffold author decides whether to fix manually in v0 or accept. A summary report is written to `<scaffold>/docs/v0-import-report.md` so the author has actionable findings outside CLI output.

The motivation: v0 produces inconsistencies and bugs that no human notices until an agent later integrates broken code (broken imports, type errors, navigation links pointing nowhere, inconsistent component names, missing variants). Catching these at import time is much cheaper than catching them mid-orchestration.

#### Scenario: TypeScript type-check
- **WHEN** validation runs
- **THEN** the importer executes `npx tsc --noEmit` in the v0-export directory (uses v0's own tsconfig.json)
- **AND** any reported type errors are written to the import report under `## TypeScript Errors`
- **AND** type errors are NON-BLOCKING by default (warn) but BLOCKING when `--strict` flag is passed

#### Scenario: Build smoke test
- **WHEN** validation runs AND `--no-build-check` is NOT passed
- **THEN** the importer executes `pnpm install --frozen-lockfile && pnpm build` in the v0-export directory
- **AND** build failure is BLOCKING (the importer exits non-zero — broken v0-export cannot be the design source of truth)
- **AND** stderr from build is captured into the report

#### Scenario: Component naming consistency
- **WHEN** validation runs
- **THEN** the importer scans all React component declarations and groups by semantic similarity (heuristic: lowercase + token-similarity threshold)
- **AND** if multiple components have similar names suggesting same concept (e.g. `Card`, `ProductCard`, `ItemCard` all appear), a WARNING is added to the report under `## Naming Inconsistencies`
- **AND** the warning lists each component with its file path and a suggestion ("consider standardizing on a single name")
- **AND** naming inconsistency is NON-BLOCKING — the report is informational

#### Scenario: Navigation link integrity
- **WHEN** validation runs
- **THEN** the importer scans every `<Link href="/...">` and `router.push("/...")` call in the v0-export
- **AND** for each href, checks whether the destination route exists (`app/<path>/page.tsx`)
- **AND** broken links are reported as `## Broken Navigation Links` with source file + line + href
- **AND** orphan pages (routes with no incoming link) are reported as `## Orphan Pages` with route path
- **AND** these issues are BLOCKING by default (broken navigation is a clear bug) — overridable with `--ignore-navigation` flag

#### Scenario: Variant coverage consistency
- **WHEN** validation runs
- **THEN** for each shared component (header, footer), the importer detects state variants by inspecting JSX conditional logic and prop types
- **AND** if a variant exists in some pages but not others (e.g. `signed-in` Header on /fiokom but anonymous Header on /kavek), it is reported as `## Variant Coverage Gaps` — NON-BLOCKING WARNING
- **AND** the report explicitly notes: "this may be intentional; review manually"

#### Scenario: shadcn primitive usage consistency
- **WHEN** validation runs
- **THEN** the importer counts occurrences of shadcn primitives (`Button`, `Card`, etc.) and direct HTML equivalents (`<button>`, `<div className="rounded-lg border">`)
- **AND** if both are used in similar contexts across different files, a WARNING lists the files and recommends standardizing on shadcn
- **AND** this is NON-BLOCKING (some HTML element use is legitimate)

#### Scenario: Report file is the artifact
- **WHEN** validation completes
- **THEN** `<scaffold>/docs/v0-import-report.md` is written with all findings grouped by severity
- **AND** the report includes counts: `## Summary — Errors: N, Warnings: M, Info: K`
- **AND** the report timestamps + records the source URL/ZIP and ref/SHA so it's reproducible
- **AND** the importer prints the report path on stdout so the user knows where to read
- **AND** the report SHALL be gitignored in scaffolds (it changes on every re-import — committing it would create noisy diffs); the importer's deploy step adds `docs/v0-import-report.md` to scaffold's `.gitignore` if not already present

#### Scenario: Hard error fail-fast
- **GIVEN** validation found a BLOCKING issue (build failure, broken navigation, or `--strict` type error)
- **WHEN** the importer would continue to manifest generation
- **THEN** it stops and exits non-zero
- **AND** prints the report path + a one-line summary of what failed
- **AND** the user must fix in v0 (or pass override flag) and re-import

#### Scenario: --strict-quality flag promotes ALL warnings to errors
- **GIVEN** the user passes `--strict-quality` to `set-design-import`
- **WHEN** validation finds ANY warning-level issue (naming inconsistency, variant coverage gap, shadcn primitive consistency, non-strict type errors)
- **THEN** all warnings are treated as BLOCKING errors
- **AND** the importer exits non-zero with the report path
- **AND** scaffold authors who want zero-warning designs use this flag in CI to enforce strict quality

### Requirement: Idempotent re-import

Re-running `set-design-import` on the same scaffold with a new ZIP SHALL produce a clean state without manual cleanup.

#### Scenario: Re-import replaces v0-export entirely
- **GIVEN** a scaffold already has `v0-export/` from a previous import
- **WHEN** the importer runs again with `--force` and a new ZIP
- **THEN** the previous `v0-export/` is fully removed before extraction
- **AND** stale files from the previous export do NOT remain
- **AND** manifest regenerates with manual overrides preserved
