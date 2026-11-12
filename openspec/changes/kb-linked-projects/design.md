## Context

`set-kb` searches one project: the git root it runs in, with that root's `kb.json`. Every
corpus decision (language, stemming, channels, the reserved lane and its quota) is a
per-corpus measurement, made by the corpus owner on its own golden set. The project registry
(`~/.config/set-core/projects.json`) already names every repository set-core knows,
including data repositories registered without a deploy.

## Goals / Non-Goals

**Goals:** an agent in project A finds an answer that lives in project B's knowledge, with the
same query, and can open it. B is ranked the way B's owner tuned it.

**Non-Goals:** merging two corpora into one ranking; following links transitively; writing
anything into B other than the index B's own searches already maintain; a remote (other
machine) corpus.

## Decisions

### D1 — Search B in B's index, not B's files in A's index

The upstream engine's merged sources would make B's folders roots of A's index. That was
rejected for two reasons. It duplicates B's chunks into every index that names it. And it
ranks B with A's configuration: a Hungarian corpus tuned with stemming and a lane quota would be searched
as English, flat. Loading B as a project (`load_project(B)`) and calling the same
`search_project` keeps B's configuration whole and reuses B's index, the one B's own searches
refresh.

### D2 — Separate blocks, not one merged ranking

BM25 scores from two indexes are not comparable: corpus size, document lengths and field
weights differ. Interleaving them would produce an order that looks meaningful and is not. So each
linked project is its own block, and its hits carry `project`. The caller sees where a hit came
from, and the main page's ranking is unchanged.

### D3 — The registry name is the address; the link is the permission

`project` is a registry name rather than a path, so `kb.json` (committed) carries no
machine-local path. The same name resolves on every machine that registered B. `get --project`
accepts only names the config links, so an agent cannot use it to read an arbitrary
repository on the machine.

### D4 — Failures are page content

A link that cannot be searched becomes a `LinkedSearch.error`, rendered as `NOT SEARCHED`.
A silently skipped link reads as "B has nothing on this", which is a false absence (see
`.claude/rules/evidence-discipline.md`). Every exception in a linked search is caught for
the same reason: A's own page must still come back.

### D5 — One level

B's own `linked` is not followed. Transitive links make the searched set depend on
configuration nobody in A can see, and they open cycles. A's config lists what A searches.

### D6 — The caller's filters stay home

`--root`, `--channel`, `--scope` and `--exclude-path` name A's roots, channels and scopes.
Applied to B they would match nothing or the wrong thing. Only the link's `scope` (in the
stored `<name>=<value>` form) reaches B.

## Risks / Trade-offs

- **A search in A refreshes B's index.** That is a write into B's `.set/`, the same one
  B's own search makes. The ignore guard applies there unchanged. A B whose `.set/` is not
  ignored shows as `NOT SEARCHED`, it is not written.
- **Latency adds up per link.** A no-change refresh measured 0.6–0.8 s on a 5.7k-file corpus,
  so each link costs about that much. `--no-linked` exists for the caller that knows it does not need B.
