---
name: set:kb
description: Search the project knowledge base — ranked section-level search over the project's markdown (notes, decisions, meeting transcripts, archived changes). Use before claiming something has no precedent, before planning a change, and whenever a grep returns more files than you will read. Zero hits describe the index, not the world.
---

# set:kb — the project knowledge base

`set-kb` searches every indexed markdown file of THIS project and returns
ranked SECTIONS with a score — not files. The `kb_search` / `kb_get` MCP tools
run the same engine; this skill is the manual, per-command way in.

## When to search

- Before claiming there is no source, precedent or prior decision — search first.
- Before planning a change: the topic may already be decided, tried or measured.
- When a grep returns more files than you will read — the ranking has already done that work.

## How to search

```bash
set-kb search "<topic words>"                      # the text page
set-kb search "<topic words>" --json               # the stable contract for scripts
set-kb search "<topic>" --root <root>              # narrow to one configured root
set-kb search "<topic>" --channel <name>           # …or one channel
set-kb search "<topic>" --scope <name>=<value>     # …or one captured scope
set-kb search "<topic>" --exclude-path <fragment>  # drop a path from the page
```

## How to read a hit

- `path` is repository-relative and `set-kb get <path>` accepts it unchanged;
  `set-kb get <path> --section "<heading path>"` prints that section verbatim.
- `headingPath` locates the section; `suppressedSections` counts further
  matching sections of the same file; `duplicateCount` marks identical content
  at other paths.
- `channel` and `scope` say which configured layer a hit came from —
  `set-kb sources` lists them with the project's own descriptions.
- `score` is BM25 (lower = better); compare only within one result page.

## What zero hits means

Zero hits describe THE INDEX, not the world. The page says so, names the exact
query, and lists the exclusions in force. When a corpus looks wrong run
`set-kb doctor`; when a specific document must be findable run
`set-kb findability`.
