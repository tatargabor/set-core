## Context

The engine (`lib/set_kb/`) is a stdlib-only Python port of an MIT upstream. It indexes with
FTS5 `porter unicode61`: accents are folded, and an English stemmer is applied on both the
index and the query side. The language seam (`LanguagePack.stem`) exists, but no shipped pack
fills it. The `hu` pack carries only stopwords.

A sibling search plugin wraps the same upstream engine in TypeScript. It solved the
same miss on the query side (`src/hu.ts`): a short folded suffix list, stripped breadth first
for three steps, and the longest stem the index holds added as an extra ORed term. It is
measured there on a 14k-file office archive: a single inflected word went from 0 hits to 8–10.

## Goals / Non-Goals

**Goals:** an inflected or accent-dropped Hungarian query term reaches the sections that spell
another form of the same word, and English queries do not get worse. No re-index, no schema change.

**Non-Goals:** index-side stemming; a dictionary morphology; changing any existing project's
ranking by default; tuning a corpus's lane settings.

## Decisions

### D1 — Query-side only, as a prefix term

A custom FTS5 tokenizer cannot be registered from the Python `sqlite3` module, so an
index-side Hungarian stemmer would mean a second stemmed column. That brings a schema bump,
a forced re-index of every corpus, and new bm25 weights. Instead the query term becomes
`"<stem>"*`.

Measured (2026-11-12, in-memory FTS5, `porter unicode61`): FTS5 runs the porter stemmer over a
prefix token too. `"keres"*` matched the indexed term `kere` (from `kérés`), and `"vonalkod"*`
matched `vonalkod`, `vonalkodot` and `vonalkodo` (from `vonalkódos`). Because porter only
shortens a token, a stem prefix still matches.

Alternative rejected: the plugin's "longest stem the index holds, as an exact term". On this
corpus the longest stem present for `vonalkodot` is `vonalkodo`, the porter form of a
*different* word (`vonalkódos`). An exact term would miss the base form. A prefix of the
shortest stem covers all of them at once.

Alternative rejected: keep the term as written AND add the prefix (`"vonalkódot" OR
"vonalkod"*`). Measured on 25 English queries, that counted every widened term twice in bm25.
It tilted multi-term queries toward that one word: 8/25 English top-10s stayed unchanged,
against 19/25 when the prefix replaces the term. The prefix already covers the term as written.

### D2 — The suffix list is the plugin's, plus the assimilated instrumental

Prototype stage, on 16 Hungarian + 9 English queries over the corpus (the prototype was a
throwaway; the numbers are the evidence):

| variant | hu target in top 10 | en top-3 |
|---|---|---|
| today (no stemming) | 4/16 | 8/9 |
| Snowball Hungarian, prefix | 15/16 | 8/9 (ranks identical) |
| plugin suffix list + instrumental rule, prefix | **16/16** | 8/9 (ranks identical) |

The two stemmers tie within one query. The plugin list wins on two grounds. It is an
existing, measured mechanism, and adopting one is the rule here. And it needs no 700 lines of
vendored generated code. Snowball over-stems in ways that only the prefix arm hides:
`vonalkód` → `vonalkó`, `kódot` → `kó`. The instrumental rule (`-al`/`-el` after a doubled
consonant: `kóddal` → `kód`) closes the one miss the plugin list had.

### D3 — Shortest stem, minimum five letters; an unchanged ASCII word stays as written

The shortest stem gives the widest reach, so the floor decides the noise. At four letters,
English words of a bilingual corpus lost too much (`content` → `cont`*, `digit` → `digi`*), and
so did Hungarian ones (`termékek` → `term`*, which reaches `terminal`). Five kept every Hungarian
hit on the measured set. A word with nothing stripped is widened only when it carries an accent.
An accent marks the word as Hungarian (`vonalkód` → `vonalkod`* reaches `vonalkódot`). A plain
ASCII word with nothing stripped is left alone: widening `admin` to `admin`* reached
`administrator` and moved English rankings for no Hungarian gain.

Final measurement with the shipped code, on 19 Hungarian queries (single inflected words,
accent-dropped forms, whole questions) and 25 English queries:

| | hu target in top 10 | English top-10 unchanged | English #1 unchanged |
|---|---|---|---|
| stemming off | 7/19 | — | — |
| stemming on | **17/19** | 19/25 | 22/25 |

The two Hungarian misses are cross-language: their target pages are English and never spell
the Hungarian word, so no stemmer reaches them. The three changed English #1s look neutral or
better (for example an invoice-XML question now leads with the tax authority's own API doc).
None of them was judged against a labelled set.

### D4 — Opt-in key, loud when it cannot apply

`stemming: true` turns it on, and the default is `false`. The previous `hu` verdict ("no
measured benefit") was measured on another corpus. Changing that corpus's ranking silently
would repeat the same mistake in the other direction. The key is query-side only, so it stays
out of the corpus-config hash: flipping it needs no re-index. `stemming: true` with a pack that
has no stemmer is a config error, because silently ignoring it would read as "stemming on, no gain".

### D5 — The stem leaves `tokenize`

`tokenize` applied `pack.stem` to every token, including body tokens in the coverage rerank, PRF
and MMR. No pack filled it, so moving the call is behaviour-neutral. Keeping it there would
compare stems against raw body tokens. Those paths stay on raw tokens, because the rerank's
`has_stem` is already prefix-tolerant in both directions (`vonalkodot` ↔ `vonalkod`).

## Risks / Trade-offs

- [A prefix over-matches an unrelated word sharing five letters] → bounded by the floor. 6 of 25
  English top-10s moved; that is why the switch is opt-in and measured per corpus.
- [An English word with a Hungarian-looking ending is stripped (`webhook` → `webho`*,
  `pagination` → `pagin`*)] → the prefix still matches the word itself. No suffix stripper can
  tell the two languages apart without a dictionary, and a dictionary is a non-goal.
- [Top-3 placement of a short "own words" page is a lane decision, not a stemming one] → on the
  measured corpus a wiki hit lands at exactly rank 4, because `laneQuota: 0.3` gives the reserved
  lane its first slot at position 4. With stemming on and `laneLeadMargin: 0.5`, Hungarian top-3
  went from 0/19 to 12/19, and English wiki targets from 8/9 to 9/9. That goes to the corpus
  owner as a config choice and is not changed here.

## Migration Plan

Nothing to migrate. A project opts in with `"language": "hu", "stemming": true` in
`set/knowledge/kb.json`, then compares with `set-kb eval` before and after. To roll back, remove the key.

## Open Questions

- Whether the plugin should adopt the prefix form. It cannot from a wrapper, because the upstream engine
  quotes every term. That is the plugin's decision, and it is reported to them.
