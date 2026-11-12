## 1. Language seam and the Hungarian stemmer

- [x] 1.1 `lib/set_kb/lang.py`: document `stem` as token → folded prefix stem or None, query side only, behind `stemming`
- [x] 1.2 `lib/set_kb/lang_hu.py`: folded suffix list + breadth-first `stems()` (three steps, no form under `MIN_STEM`), the assimilated-instrumental rule incl. digraphs, `prefix_stem()`; fill `hungarian_pack.stem`
- [x] 1.3 `lang_hu.py` docstring: replace the "deliberately absent" verdict with the new measurement, keeping the old one scoped to its own corpus

## 2. Match expression and config

- [x] 2.1 `lib/set_kb/types.py`: `SearchOpts.stemming` (default False)
- [x] 2.2 `lib/set_kb/search.py`: `tokenize` stops applying the stem; `to_match(q, lang, stemming)` replaces a widened term with `"<stem>"*`; all three callers pass `opts.stemming`
- [x] 2.3 `lib/set_kb/config.py`: `stemming` default, boolean validation, a loud error for a pack without a stemmer, carried into `search_options`, kept out of `corpus_config_hash`

## 3. Tests

- [x] 3.1 `tests/unit/test_kb_stemming.py`: stemmer cases (inflected, plural+accusative, accented base, instrumental, digraph instrumental, accent-dropped), the floor, unchanged ASCII left alone
- [x] 3.2 Match-expression tests: off by default unchanged, replacement, two forms collapse, en pack unchanged
- [x] 3.3 Config tests: default off, reaches the search options, loud without a stemmer, boolean only, no re-index
- [x] 3.4 End-to-end recall on a one-form-per-section corpus, one test per spec scenario, plus no unrelated section pulled in
- [x] 3.5 `tests/unit/test_kb_lang.py`: the "pack has no stemmer" assertion follows the decision
- [x] 3.6 Mutation check: with the widening disabled in `to_match`, 5 of the new tests fail; restored and compared byte for byte
- [x] 3.7 The whole kb suite: `tests/unit/test_kb_*.py` 255 passed (baseline before the change: 225 passed)

## 4. Measurement and docs

- [x] 4.1 Measure on a real Hungarian business corpus: 19 Hungarian queries 7/19 → 17/19 in the top 10; 25 English queries 19/25 top-10 unchanged, 22/25 #1 unchanged; recorded in design D3
- [x] 4.2 `docs/reference/kb-search.md`: the `stemming` key
- [x] 4.4 Second measurement on office prose (14k-document archive, 15 clerk prompts, ground truth): recall@10 0.400 → 0.467, hit@1 4 → 5, hit@5 5 → 6, no prompt worse; recorded in design D3. Found B-172 (document numbers split into loose tokens) and registered it
- [ ] 4.3 The corpus owner turns it on (`"language": "hu", "stemming": true`) and re-measures with `set-kb eval` on its own golden set — the owner's step, reported to them together with the `laneLeadMargin` finding
