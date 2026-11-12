## Why

The kb engine indexes with FTS5 `porter unicode61`, an English stemmer. A Hungarian word
carries its case, number and possessive as suffixes, so an inflected query term matches
only sections that spell the same inflected form. Measured on 2026-11-12 on a private Hungarian business
corpus (4.8k files, 46k chunks) where wiki pages are written in English with the
Hungarian domain word beside them: `vonalkód` put the barcode wiki page at rank 4, and
`vonalkódot` did not put it in the top 30. Of 19 Hungarian queries (single inflected
words, accent-dropped forms, whole questions), only 7 found their target page in the top 10.

The earlier verdict in `lib/set_kb/lang_hu.py` ("no measured benefit" from a suffix
stripper) was measured on a different corpus, and it does not cover this one: here the
miss is total, not within noise.

## What Changes

- The Hungarian language pack gains a suffix stemmer. It adopts an existing, measured
  mechanism: the suffix list and breadth-first stripping of the Hungarian module of a
  sibling search plugin built on the same upstream engine. It adds one rule that module lacks: the assimilated instrumental
  (`kóddal` → `kód`).
- When stemming is on, each query term is sent to FTS5 as a **prefix of its shortest
  stem of at least 5 letters** (`"vonalkod"*`), replacing the term as written. The prefix reaches every inflected form
  the index holds (`vonalkód`, `vonalkódot`, `vonalkódok`, `vonalkódos`), with no
  re-index and no schema change.
- A new config key `stemming` (boolean, default `false`) switches it on. Turning it on
  with a language whose pack has no stemmer fails config loading, naming the key and the
  language. **Opt-in on purpose:** existing `language: "hu"` projects keep today's
  ranking until they measure the change on their own golden set.
- `lang_hu.py`'s docstring changes to the new measurement. The old verdict stays,
  scoped to the corpus it was measured on.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `kb-search-engine`: an opt-in stemmed query path for a language pack that has a
  stemmer. Added as a new requirement. The capability's base spec is still in the
  unarchived `kb-search` change, so nothing in the existing requirements changes.

## Impact

- `lib/set_kb/lang.py`, `lib/set_kb/lang_hu.py`: the stemmer seam gets content.
- `lib/set_kb/search.py`: `to_match` builds prefix terms when stemming is on, and `tokenize`
  stops applying the stem (no shipped pack filled it, so no behaviour change).
- `lib/set_kb/config.py`: the `stemming` key, validated, kept out of the corpus-config hash
  (query-side only, so turning it on needs no re-index; design D4).
- `docs/reference/kb-search.md`: the key is documented.
- No new dependency (stdlib only, as the engine requires).
- Not touched: the index, the schema, the MCP `kb_search` surface (it shells out to `set-kb`).
