## Context

set-core maps short model names to Anthropic model ids in one place, `DEFAULT_MODEL_IDS`
in `lib/set_orch/providers/defaults.py` (mirrored in `bin/set-common.sh`). The start
dialog offers the `models` list of the machine's `providers.json`, which is a copy made at
migration (B-156). When Anthropic publishes a model, nothing tells anyone. Measured
2026-09-29: upstream lists `claude-sonnet-5-5` while `sonnet` → `claude-sonnet-4-6`.

What is reachable without a key, measured the same day:

- `https://platform.claude.com/docs/en/about-claude/models/overview.md` returns 200,
  `text/markdown`, 17 KB. It is first-party, and its table has "Claude API ID" and
  "Claude API alias" rows, one column per current model.
- `https://models.dev/api.json` (200, 5.2 MB) is community-maintained and has release dates.
- `https://openrouter.ai/api/v1/models` (200, 755 KB) is a third-party router with its own ids.
- The models API needs an API key. This machine has none, only the agent CLI's
  subscription login, which belongs to another tool.

## Goals / Non-Goals

**Goals:** say, on this machine, "Anthropic has X and set-core does not", and "set-core
ships Y and this machine's config does not offer it". Never report "up to date" without
having measured.

**Non-Goals:** editing any file, or choosing what `sonnet` should mean. Those are reviewed
set-core commits. Other providers are out too, as are background polling and push
notifications.

## Decisions

1. **Source: the first-party overview page, not models.dev or OpenRouter.** Anthropic's own
   page is the authority on which ids exist, and it is small. The third-party lists add
   a dependency on someone else's curation. They are the fallback if the page moves, and
   that is a code change, not a runtime fallback: a silent fallback would change the
   answer's authority without saying so.
2. **Parse two anchored table rows, not a page-wide regex.** A page-wide
   `claude-[a-z0-9-]+` match picks up link slugs (`claude-prompting-best-practices`,
   `claude-in-amazon-bedrock`). That is the "prose read as fact" defect class. The
   parser finds lines whose first cell is exactly `Claude API ID` or
   `Claude API alias` and takes the backticked cell values by column. Zero rows found
   means `unknown`.
3. **Coverage by exact id, alias, or pass-through family.** `fable` is deliberately passed
   through to the agent CLI without an id (see `defaults.py`), so any `claude-fable-*`
   is covered by it. Every other family must have the exact id as a mapping value. Otherwise a
   new Opus would be hidden by the `opus` shorthand still resolving to the previous one,
   which is exactly the gap to report.
4. **Cache in `~/.cache/set-core/upstream-models.json`, 24 h.** It holds public data only,
   so the persistence boundary is not crossed. The cache stores the parsed ids and the fetch
   time, not the page. A failed fetch never overwrites a good cache.
5. **The route reads through the same function with a 10 s timeout.** It is a sync FastAPI
   route, so it runs in the thread pool and cannot block the event loop. With the cache
   warm it makes no network call.
6. **The dialog shows the notice only for `behind` or `unknown`.** It is a sentence
   inside the dialog, with no badge and no reflow of the header, following the compact
   rule. `current` shows nothing. A failure to load the report is shown as `unknown` and
   never hides the models or the start button.
7. **Layer:** `upstream.py` sits in `lib/set_orch/providers/` beside `defaults.py`. The
   URL and parser are keyed to the `anthropic` provider name, so the shape extends to
   another provider later without core changes.

## Risks / Trade-offs

- [The docs page changes shape] → it becomes `unknown` with a reason, and the CLI exits 2.
  A test holds a fixture of the current table, and another holds the shape-change case.
- [A model listed upstream that set-core deliberately does not ship] → it keeps showing
  `behind`. That is acceptable for now; an ignore list is a later change if it happens.
- [Network egress from the dashboard] → one GET per day to a public page, no data sent.
