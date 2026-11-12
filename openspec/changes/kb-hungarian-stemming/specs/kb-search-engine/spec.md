## IN SCOPE
- A Hungarian suffix stemmer in the `hu` language pack
- Stemmed query terms sent to FTS5 as prefix terms, behind an opt-in `stemming` config key
- Loud config failure when stemming is requested for a language without a stemmer

## OUT OF SCOPE
- Index-side stemming, a second tokenizer, or any schema change
- A full morphological analyser (e.g. a dictionary-based one)
- Changing the default ranking of an existing `language: "hu"` project
- The reserved-lane quota and lead margin a corpus chooses (a corpus config decision)

## ADDED Requirements

### Requirement: A language pack with a stemmer can widen query terms to their stem's prefix

When the configuration sets `stemming: true`, the engine SHALL send each query term to the
full-text match as a prefix term built from that term's shortest suffix-stripped stem of at
least five letters, accent-folded, in place of the term as written. When no stem reaches five
letters, or when nothing was stripped from a term written in plain ASCII, the term SHALL be
sent as it is. When `stemming` is absent or `false`, the query SHALL be built exactly as without
this requirement. Setting `stemming: true` with a language whose pack has no stemmer SHALL
fail configuration loading, naming the `stemming` key and the language.

#### Scenario: An inflected query finds the base form
- **WHEN** a corpus holds a section spelling only `vonalkód`, the language is `hu`, stemming is on, and the query is `vonalkódot`
- **THEN** that section is among the hits

#### Scenario: A base-form query finds an inflected form
- **WHEN** a corpus holds a section spelling only `vonalkódokat`, the language is `hu`, stemming is on, and the query is `vonalkód`
- **THEN** that section is among the hits

#### Scenario: Accents dropped by the user
- **WHEN** the query is `szamlakat` and a section spells only `számla`, with stemming on
- **THEN** that section is among the hits

#### Scenario: The assimilated instrumental
- **WHEN** the query is `vonalkóddal` and a section spells only `vonalkód`, with stemming on
- **THEN** that section is among the hits

#### Scenario: Off by default
- **WHEN** the language is `hu` and the config does not set `stemming`
- **THEN** the match expression is the same as before this change, and `vonalkódot` does not match a section spelling only `vonalkód`

#### Scenario: A short stem is not widened
- **WHEN** a query term's every stripped stem is shorter than five letters (e.g. `árak`)
- **THEN** the term is not widened to a shorter prefix

#### Scenario: An unchanged English word is left alone
- **WHEN** stemming is on and the query term is `admin`
- **THEN** the term is matched as written, not as `admin`*

#### Scenario: Stemming requested without a stemmer
- **WHEN** the config sets `language: "en"` and `stemming: true`
- **THEN** loading fails with an error naming `stemming` and `en`
