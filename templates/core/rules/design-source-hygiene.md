# Design Source Hygiene Rule

## Operator pre-flight

Before each orchestration run, verify the design source quality:

```bash
set-design-hygiene <project-path>
# or, combined with import:
set-design-import --git <url> --ref main --with-hygiene
```

The CLI writes `docs/design-source-hygiene-checklist.md` listing 9 quality rules across 3 severity tiers:
- **CRITICAL** (blocks adoption) — broken routes, header inconsistency, MOCK arrays
- **WARN** (degrades agent quality) — i18n string leakage, action-handler stubs, type `any`
- **INFO** (potential cleanup) — placeholder image URLs, inline lambda body, mock URLs

If the CLI reports CRITICAL findings, exit code is non-zero and orchestration should pause until the operator fixes them in the design source repo (e.g. v0-design on Mac, separate git location).

## Operator workflow

1. Run `set-design-hygiene` after each design re-import.
2. Open `docs/design-source-hygiene-checklist.md`.
3. For each CRITICAL: fix in the **design source repository** (not in the consumer project — that would drift).
4. Re-run `set-design-hygiene` until 0 CRITICAL.
5. Start orchestration.

## Why design source quality matters

If the design source has bugs (e.g. v0-export's `<Link href="/bejelentkezes">` while the route is `/belepes`), every orchestrated change inherits them. Agents propagate broken routes into every page, then E2E tests fail in confusing ways. The hygiene gate catches these BEFORE agents see them, saving hours of debugging.

## Bypassing CRITICAL findings

If you must run with CRITICAL findings (e.g. last-minute v0 update with a known issue), use:

```bash
set-design-hygiene --ignore-critical
# or:
set-design-import --with-hygiene --ignore-critical
```

This logs the override clearly. The checklist is still written for your records.

## What the framework does NOT do

- The framework does NOT modify the design source repository — operator fixes manually
- The framework does NOT auto-suppress findings — every finding is surfaced
- The framework does NOT block existing orchestrations — only the next dispatch sees the latest checklist
