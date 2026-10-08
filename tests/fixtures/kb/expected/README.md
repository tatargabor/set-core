# Recorded oracle pages

One JSON file per query in `../queries.json`, in the shape the reference
engine's `search --json` prints, minus the machine-local `cwd` field:
`query`, `limit`, `hits[]` (`root`, `path`, `headingPath`, `chunkId`, `docType`,
`channel`, `score`, `snippet`, `suppressedSections`, `akaPaths`, `parent`),
`total`, `hasMore`, `exclusions`.

The differential test (`tests/unit/test_kb_oracle.py`) runs the Python engine
over a temp copy of `../corpus` with `../kb.config.json` and requires the same
hits in the same order for every page — scores are compared with a float
tolerance, everything else exactly (task 2.9).

## Pinned reference state

The pages were recorded on 2026-10-07 with the reference TypeScript engine
frozen at the following state of its repository:

| | |
|---|---|
| last commit touching the engine directory | `2ab5aaf622914edd1cde9105495f306fd67a5a66` (2026-09-30) |
| repository HEAD at recording time | `583d8f6b986485c7b706fb08f3981286375e5858` |
| working tree over `scripts/kb/` | clean (no uncommitted engine edits) |

Re-recording at a different state is a deliberate re-pin: run
`../record_expected.py` and update this file in the same commit.
