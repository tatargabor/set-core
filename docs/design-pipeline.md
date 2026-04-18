# Design Pipeline (v0-only)

set-core's design pipeline treats a v0.app export as the authoritative
source of UI truth. Agents **integrate** v0's TSX into the project rather
than reconstructing it from a markdown spec. Visual fidelity is enforced
by the `design-fidelity` integration gate.

## Lifecycle

```
scaffold author           set-core framework              agent
──────────────             ──────────────────              ─────
(1) author v0 design
    in v0.app
(2) push to git repo
    (or export ZIP)
                           (3) set-design-import
                               clones / unzips → v0-export/
                               generates design-manifest.yaml
                               validates quality
                           (4) runner deploys to
                               consumer project
                                                            (5) copy v0 TSX
                                                                adapt data layer
                                                                commit
                           (6) design-fidelity gate
                               skeleton check → screenshot
                               diff → pass/fail
```

## Scaffold setup

In `scaffold.yaml`:

```yaml
project_type: web
template: nextjs
ui_library: shadcn

design_source:
  type: v0-git                  # or v0-zip
  repo: https://github.com/owner/v0-design-repo.git
  ref: main                     # branch / tag / commit SHA
```

Gitignore `v0-export/` in the scaffold — the importer materializes it at
deploy time.

Author `docs/content-fixtures.yaml` with HU seed data for the fidelity
gate's reference render.

Run once:

```bash
set-design-import --scaffold path/to/scaffold
# or force re-import:
set-design-import --scaffold path/to/scaffold --force
# or regenerate manifest after hand-editing v0-export:
set-design-import --scaffold path/to/scaffold --regenerate-manifest
```

The importer validates structure (App Router, components/ui/ when
`ui_library: shadcn`, globals.css), syncs globals.css to
`shadcn/globals.css`, and writes `docs/design-manifest.yaml`.

## CLI flags

| Flag | Effect |
|------|--------|
| `--git <url>` | override scaffold.yaml source, use this git URL |
| `--ref <sha>` | pin to branch/tag/commit |
| `--source <zip>` | ZIP fallback |
| `--force` | wipe + replace existing `v0-export/` |
| `--regenerate-manifest` | manifest-only refresh (no re-import) |
| `--strict` | TypeScript type-check errors become blocking |
| `--no-build-check` | skip pnpm build smoke test |
| `--ignore-navigation` | demote broken-link errors to warnings |
| `--strict-quality` | promote ALL warnings to blocking errors |

## Manifest coverage contract (decompose)

When `docs/design-manifest.yaml` exists AND the plan has any
`design_routes` entries, the planner MUST bind every manifest route:

```json
{
  "changes": [
    {
      "name": "homepage",
      "design_routes": ["/"],
      "scope": "..."
    },
    {
      "name": "catalog",
      "design_routes": ["/kavek", "/kavek/[slug]"],
      "scope": "..."
    }
  ],
  "deferred_design_routes": [
    {"route": "/admin/settings", "reason": "Phase 2"}
  ]
}
```

`validate_plan()` (via `WebProjectType.validate_plan_design_coverage`)
rejects plans that leave a route unassigned or multi-assigned.

## Design-fidelity gate

Registered by `WebProjectType`, runs `pre-merge, position=end,
run_on_integration=True`. Three phases:

1. **Skeleton check** — route inventory + shared file existence +
   component decomposition. Fast, no build. Fails → `skeleton-mismatch`.
2. **Build reference + agent** — v0-export rendered with fixtures in a
   temp dir; agent worktree built in place. Failures →
   `reference-build-failed` / `agent-build-failed`.
3. **Pixel diff** — Playwright screenshots at 1440×900, 768×1024,
   375×667; pixelmatch diff vs threshold (default 1.5% / 200px floor).

### Gate status codes

| Status | Meaning | Behavior |
|--------|---------|----------|
| `skipped-no-design-source` | `v0-export/` absent | merge proceeds |
| `manifest-missing` | scaffold bug | FAIL merge |
| `fixtures-missing` | scaffold/runner bug | FAIL merge |
| `reference-build-failed` | v0 code broken | FAIL merge |
| `agent-build-failed` | agent code broken | FAIL merge |
| `skeleton-mismatch` | structural drift | FAIL merge |
| `pass` | all diffs under threshold | merge proceeds |
| `fail` | at least one route exceeds threshold | FAIL + diff images |

### Single explicit override

```yaml
# set/orchestration/config.yaml
gates:
  design-fidelity:
    warn_only: true
```

Downgrades any failure to warning; INFO logs the downgraded failure list
every run so it doesn't persist silently.

## Authentication for private design repos

v0-git mode delegates all authentication to system git. Common options:

### SSH key (recommended)

```bash
ssh-add ~/.ssh/id_ed25519   # confirm key is in agent
ssh-add -l
```

Use an SSH-form URL:

```yaml
design_source:
  type: v0-git
  repo: git@github.com:org/v0-design.git
```

### GitHub PAT

```bash
export GITHUB_TOKEN=ghp_...
```

The git credential helper picks this up when cloning `https://github.com/...`.

### GitLab / Bitbucket / self-hosted

Same workflow as GitHub — set up the provider's native auth
(`GITLAB_TOKEN`, credential helper, SSH deploy key). The importer just
shells out to git, so whatever `git clone <url>` accepts works.

### Deploy keys

For a locked-down single-repo setup, add a deploy key to the v0 repo
and point your SSH config at it:

```
# ~/.ssh/config
Host github-v0-design
  HostName github.com
  User git
  IdentityFile ~/.ssh/v0_design_deploy_ed25519
```

Then use `git@github-v0-design:org/repo.git` as the URL.

### Troubleshooting

`git clone` exit 128 → the importer prints a detailed error listing all
four auth options above. Check that:

1. The URL is correct (try `git ls-remote <url>` manually)
2. Your SSH agent has the right key (`ssh-add -l`)
3. Env var is actually exported (`env | grep -i token`)
4. The account/key has access to the repo

## Refactor policy

See `templates/core/rules/design-bridge.md` (deployed as
`.claude/rules/design-bridge.md` in consumer projects) for the full
allowed/forbidden list.

## Migration from Figma

The previous Figma pipeline (`.make` binary → markdown spec → agent
re-implements) is removed entirely in the `v0-only-design-pipeline`
change. Consumer projects with existing `.make` files must:

1. Open the design in v0.app using prompts from `docs/v0-prompts.md` as a starting point.
2. Push the v0 result to a git repo (v0's native "Push to GitHub" feature).
3. Update `scaffold.yaml`:
   - Remove any `figma_url` or legacy design fields
   - Add a `design_source: { type: v0-git, repo, ref }` block
4. Delete obsolete files: `docs/design.make`, `docs/design-system.md`, `docs/design-brief-aliases.txt`.
5. Optionally rewrite `docs/design-brief.md` as a 1-page non-authoritative vibe note.
6. Run `set-design-import --scaffold <path>` to materialize `v0-export/` + manifest.

`set-project init` detects `.make` files and emits a clear migration
error pointing to this section.
