## 1. The defaults module

- [x] 1.1 Create `lib/set_orch/providers/defaults.py`: the catalogue tuple, the default `model_ids` mapping (values moved verbatim from `subprocess_utils._MODEL_MAP`, `fable` deliberately absent, comments moving with the data), no set_orch imports [REQ: the-mapping-has-one-source]
- [x] 1.2 Re-point `config.ANTHROPIC_MODEL_NAMES` / `MODEL_NAME_RE` at the defaults module, keeping the public import paths working [REQ: the-mapping-has-one-source]
- [x] 1.3 Delete `subprocess_utils._MODEL_MAP`; `resolve_model_id` reads the defaults module, signature and pass-through unchanged [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data]

## 2. The declaration field

- [x] 2.1 `providers/config.py`: parse and validate an optional `model_ids` block on a provider declaration — keys within the catalogue, values non-empty strings; malformed block refused by name [REQ: a-provider-declaration-carries-everything-needed-to-launch-it]
- [x] 2.2 Whole-block semantics: a declared `model_ids` replaces the default for that provider; no merge; empty block means no translation [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data]

## 3. The resolver

- [x] 3.1 Launch-plan translation resolves through the effective map (declared block, else the shipped default for that provider name, else none); delete `MODEL_MAP_PROVIDERS` [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data]
- [x] 3.2 `set-providers show` displays each provider's effective id mapping (never a credential) [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data]

## 4. Migration and templates

- [x] 4.1 `migrate.build` writes the anthropic declaration with the full catalogue and an explicit `model_ids` block [REQ: the-mapping-has-one-source]
- [x] 4.2 Update the default-config templates: README Quick Start, `docs/reference/configuration.md`, `.claude/skills/set/glm/SKILL.md` [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data]

## 5. Tests and verification

- [x] 5.1 Resolver tests: declared anthropic without block → default pins; declared block → whole replacement, unmapped name passes through; undeclared provider → loud refusal untouched [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data]
- [x] 5.2 `--model fable` passes through untranslated [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data]
- [x] 5.3 No-second-copy test: `subprocess_utils` no longer resolves a private map; validators, resolver and migrate read the same module [REQ: the-mapping-has-one-source]
- [x] 5.4 Existing-config compatibility: a pre-change `providers.json` (no `model_ids`) loads and launches exactly as before [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data]
- [x] 5.5 Full provider suites green; stash-and-rerun proof on the new whole-replacement and pass-through tests [REQ: a-provider-declaration-carries-everything-needed-to-launch-it]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the configuration declares `anthropic` with a catalogue and no `model_ids` block THEN launch plans deliver CLI ids from the shipped default mapping [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data, scenario: a-declared-anthropic-provider-without-its-own-map-uses-the-default]
- [x] AC-2: WHEN an anthropic declaration carries its own `model_ids` block THEN every catalogue name resolves through that block, and a name the block does not map is delivered unchanged rather than falling back to the default [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data, scenario: a-declared-map-replaces-the-default-whole]
- [x] AC-3: WHEN the configuration file is absent or does not declare the requested provider THEN resolution fails loudly and the default id mapping plays no part [REQ: the-anthropic-id-mapping-ships-as-default-configuration-data, scenario: an-undeclared-provider-is-never-conjured-from-the-default]
- [x] AC-4: WHEN an entry in the shipped default mapping changes THEN the validator, launch plans and a subsequent migration all deliver the new pinning with no second table to update [REQ: the-mapping-has-one-source, scenario: re-pinning-a-short-name-changes-every-consumer-together]
- [x] AC-5: WHEN a provider's declared `model_ids` block changes one of its pins THEN launches deliver the new pinning on next start with no framework code change [REQ: a-provider-declaration-carries-everything-needed-to-launch-it, scenario: an-id-mapping-is-a-data-edit]
