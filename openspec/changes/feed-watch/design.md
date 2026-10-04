## Context

A consumer project shipped a first version on 2026-10-04: a skill, a ~330-line helper script with
the subcommands `seen`, `check-new`, `digest`, `lint` and `panel`, a Claude Code plugin pane, and
a rubric README. It works, and its owner uses it. This change gives the mechanism a home in
set-core. Under this repo's integration rules the consumer's shape is adopted and generalised,
not replaced. **A design that would make the consumer rewrite its existing item files has
failed.**

Limits measured in the first version, which are constraints here and not open questions:

- **A background Chrome tab does not render the feed.** It showed one post and then loading
  skeletons. Collection needs the window in front.
- **FleetView has no plugin API for a custom panel.** The scheduled prompt is a Claude Code plugin
  pane instead.
- **A cloud routine cannot collect.** Collection needs the local Chrome and its logged-in session.

## Goals / Non-Goals

**Goals:**
- One generic mechanism: collect, store, dedupe, score, digest, draft and gate, with every
  domain-bearing input declared by the project.
- The consumer's current files and rubric work with only a declaration file added.
- Read-only towards the source, always. The human is the only sender.
- Off unless the project opts in to the module **and** the user opts in on their own machine.

**Non-Goals:**
- Any posting, commenting, reacting, messaging or sending. This is not deferred: it is excluded.
- A scraper, headless browser, API client, or parallel or bulk JS extraction.
- Reading anything beyond the declared feed and its item permalinks, such as a messenger,
  notifications, profiles or other groups.
- A default rubric, a default offer, or default reply copy. set-core ships none.
- A FleetView panel. That needs a plugin API FleetView does not have, and building one is its
  own change.
- Cloud or unattended collection.

## Decisions

**D1. A feature module with its own package, not a `ProjectType`.**
`modules/` holds project-type profiles: build, test and verification rules for a tech stack. A
feed watcher is orthogonal to the tech stack, so a web project and a docs-only project can both
use it. The module therefore lives in `lib/set_feedwatch/` (domain-free Python), `bin/set-feed-watch`
(CLI), and a template the deploy installs only on opt-in. The deploy manifest already supports
optional `modules:`, and that is the opt-in carrier. *Alternative:* a `modules/feedwatch/`
ProjectType. This was rejected because it would force a project to choose between its stack
profile and the watcher.

**D2. The project declares everything domain-bearing in `.set/feed-watch.yaml`.**
```yaml
version: 1
dir: <items dir, repo-relative>
sources:
  - id: <slug>
    kind: facebook-group          # adapter
    url: <feed url>
    item_filter: <guidance file>  # which items count (e.g. "offers work", not "seeks work")
    max_items_per_run: 30
    max_age_days: 2
item_template: <file>             # optional; the header field labels, in the project's language
rubric:
  marker: <name>                  # score comment name; default "feed-watch"
  guidance: <file>                # the human-readable rubric the agent scores by
  dimensions: [{key, label, max}] # e.g. four dimensions with a max of 3
  threshold: {total_min: N, dimension_min: {<key>: M}}
drafts:
  template: <file>                # draft skeleton, voice, allowed claims: all project-side
  blocks: [<fence-lang>, ...]     # fenced blocks the gate reads
  gate: <command with {file}>     # optional copy gate; exit 0 = pass
digest:
  filename: "{date}-<suffix>.md"
```
Any label, filename suffix, marker name or language is configurable, because the consumer's
existing files use their own words for all of them. The defaults are English and neutral.
*Alternative:* hard-code the first version's format. This was rejected because it bakes one
consumer's language and vocabulary into a public framework.

**D3. The score marker is a machine line and the table is for humans.** This is kept from the
first version: `<!-- <marker>:score k=v ... -->`. The parser reads only the marker line, anchored
to the whole line, and never reads the table. An item with a malformed or out-of-range marker is
reported as **unscored**. It is never treated as a zero.

**D4. Dedupe key: the source item id first, then a normalised text hash.** The text hash is SHA-1
over the lower-cased, whitespace-collapsed verbatim body between the first two `---` lines,
truncated to 12 hex digits. This is the same algorithm as the first version, so the consumer's
existing items hash identically. A test pins it against a fixture.

**D5. The skill drives the browser and the CLI never touches the network.** Collection is agent
work through Claude in Chrome. The CLI does the deterministic parts: `seen`, `check-new`,
`digest`, `gate` and `optin`. This is the first version's split, and it keeps every deterministic
part unit-testable.

**D6. The opt-in is per account, outside every repository.** It lives in
`~/.config/set-core/feed-watch.json`, with project-keyed entries `{enabled, account, times}`. The
pane is active only when the entry is enabled **and** its account equals the session's Claude
account. The slot state lives in `feed-watch.state.json` beside it. A 30-minute lease lets only
one session show a slot. These are the first version's pure functions, and they are lifted with
their tests. `set-core` replaces the consumer's own config namespace, and `set-feed-watch optin
import` copies an existing opt-in across once.

**D7. Nothing derived from items is persisted by set-core.** Logs carry counts, ids hashed or
omitted, and stop reasons. They never carry item text, authors or contact details. Item files
live only in the consumer's tree.

## Risks / Trade-offs

- [The source's terms restrict automated collection] → Collection stays human-paced: one tab,
  the window in front, the user's own session, a per-run cap, and a stop on any challenge with no
  retry. The skill states this, and a project that opts in accepts it. The module never
  circumvents a login wall or captcha.
- [The feed markup changes and the adapter silently reads nothing] → An empty run with a visible
  feed is reported as a **stall**, never as "no new items". The report always gives seen, new,
  skipped and stop reason as separate counts.
- [The pane needs a running session and a wide enough terminal] → This is accepted from the first
  version. A missed slot stays due until the next one replaces it, and a narrow terminal gets a
  notification plus a slash command.
- [Generalising breaks the consumer's working setup] → A migration check reads the consumer's
  existing item files with only a declaration file added, and must reproduce their `seen` output
  and digest unchanged.

## Migration Plan

1. Ship the module, which is inert without a declaration file.
2. The consumer adds `.set/feed-watch.yaml` that maps its current dir, marker, labels, rubric file,
   threshold and gate. It runs `set-feed-watch seen` and `digest` and diffs them against its own
   script's output, and an empty diff is the pass condition.
3. The consumer switches its skill to the deployed one, or keeps its own skill and calls the CLI.
   Both are supported, and the consumer decides when.
4. Rollback: delete the declaration file. The consumer's own script is untouched throughout.

## Open Questions

- Should the module offer a FleetView surface later? That would be a separate change that needs a
  panel API first.
- Is a second source kind wanted soon? If not, the adapter boundary stays an interface with one
  implementation.
