# agent-provider-config Specification

## Purpose
Where provider declarations and credentials live, and what happens when that file is absent, unreadable or too permissive.

## IN SCOPE

- One machine-level file, `~/.config/set-core/providers.json`, holding every provider
  declaration, its measured launch parameters, its model catalogue, its credential, and the
  per-project overrides
- Its file permissions, and what happens when it is absent, unreadable or malformed
- The rule that adding a model or a provider is a data edit, never a framework change
- What a provider declaration must carry for the framework to be able to launch it
- The per-project override's shape, including that it may carry its own credential

## OUT OF SCOPE

- How a declaration is turned into a running process — that is `agent-provider-resolution`
- The precedence between the levels — also `agent-provider-resolution`
- Migrating an existing `glm.env` into this file — that is `agent-provider-migration`
- Anthropic OAuth account switching (`cc-accounts.json`, `set-router`), which stays a
  separate mechanism with a separate file
- The orchestration engine's role-based model chain (`agent`, `digest`, `review`, …),
  which answers a different question and is not read or written here

## Requirements

### Requirement: The provider configuration has one machine-level home

The framework SHALL read provider configuration from a single file,
`~/.config/set-core/providers.json`, honouring `XDG_CONFIG_HOME` where it is set. Every set
project SHALL inherit that configuration by reading that one file. The framework MUST NOT
copy it into a project tree, and `set-project init` MUST NOT deploy it.

The file SHALL be created with mode `0600` and the framework SHALL refuse to read it when
its mode grants any permission beyond the owner's.

#### Scenario: A project with no provider configuration of its own still resolves

- **WHEN** a project directory contains no provider configuration and the central file declares a provider
- **THEN** the framework resolves that provider for the project from the central file

#### Scenario: A world-readable configuration is refused, not silently used

- **WHEN** the configuration file's mode grants group or other permissions
- **THEN** reading it fails with an error naming the file and its mode, and no credential is read from it

#### Scenario: The deploy path never writes it

- **WHEN** `set-project init` runs against a consumer tree
- **THEN** no provider configuration file is written into that tree, and the plan does not list one

### Requirement: A provider declaration carries everything needed to launch it

A provider declaration SHALL carry the identifier by which it is selected, the model names
it accepts, and — for a provider reached over an API endpoint — the endpoint's base URL and
the credential to present. It MAY carry additional launch parameters that the framework
passes to the agent process, expressed as data rather than as code. It MAY carry a
`model_ids` block mapping its catalogue's short names to the ids the agent CLI consumes;
when the block is absent the provider's effective mapping is the framework's default for
that provider, or no translation for a provider with no default.

The set of model names in a declaration SHALL be the complete list of models valid for that
provider. Adding a model to a provider, or adding a provider, SHALL require editing this
file only, with no change to framework code.

#### Scenario: A model added to the catalogue becomes selectable

- **WHEN** a model name is added to a provider's model list in the configuration and nothing else changes
- **THEN** that model is offered for that provider and can be used to start an agent

#### Scenario: A declaration missing a required field is refused by name

- **WHEN** a provider declaration lacks a field the framework needs in order to launch it
- **THEN** reading the configuration fails with an error naming the provider and the missing field

#### Scenario: Launch parameters are data, not code

- **WHEN** a provider's declaration changes one of its launch parameters
- **THEN** the change takes effect on the next start with no framework code change and no redeploy

#### Scenario: An id mapping is a data edit

- **WHEN** a provider's declared `model_ids` block changes one of its pins
- **THEN** launches for that provider deliver the new pinning on their next start, with no framework code change

### Requirement: A per-project override may replace the provider, the model, or both

The configuration SHALL support overrides keyed by project. A project override MAY name a
different provider, a different model, or a different credential and endpoint for the same
provider.

A project override SHALL live in this central file. The framework MUST NOT read provider
credentials from a file inside a project's own working tree.

#### Scenario: A project runs on a different credential from the machine default

- **WHEN** a project override declares its own credential and endpoint for a provider
- **THEN** an agent started in that project presents that credential, and an agent started in a project without an override presents the machine default's

#### Scenario: A credential in a project tree is not consulted

- **WHEN** a project's own working tree contains a file declaring a provider credential
- **THEN** the framework does not read it, and resolution uses only the central configuration

### Requirement: An absent or unreadable configuration fails loudly and never falls back

When the configuration file is absent, unparseable, or names a provider that is not
declared, the framework SHALL report the condition with the file's path and the specific
fault. It MUST NOT substitute a built-in default provider, and MUST NOT continue with a
provider other than the one requested.

#### Scenario: A missing file names itself and the command that creates it

- **WHEN** the configuration file does not exist and a provider is requested
- **THEN** the failure names the expected path and the command that would create it, and no agent is started

#### Scenario: Malformed content is not treated as an empty configuration

- **WHEN** the configuration file exists but cannot be parsed
- **THEN** the failure says the file is malformed, and the framework does not behave as though no providers were declared

### Requirement: The Anthropic id mapping ships as default configuration data

The framework SHALL carry the Anthropic short-name → CLI-id mapping as data — the built-in
default `model_ids` for the anthropic catalogue — and SHALL apply it to a provider that the
configuration DECLARES as `anthropic` without carrying its own `model_ids` block. A
declaration that carries a `model_ids` block SHALL have that block applied WHOLE, replacing
the default for that provider; the framework MUST NOT merge a declared block with the
default, because a partial table silently missing one name delivers that name untranslated
— a wrong value rather than an error.

The default mapping MUST be applied only to a provider the configuration declares. The
framework MUST NOT use it to introduce a provider the configuration does not declare: an
absent configuration still fails loudly, with no built-in substitution.

Adding, re-pinning, or removing an entry in a provider's effective id mapping SHALL require
editing the configuration file or the shipped default data — never a change scattered
across framework code tables.

#### Scenario: A declared anthropic provider without its own map uses the default

- **WHEN** the configuration declares the provider `anthropic` with a model catalogue and no `model_ids` block
- **THEN** a launch plan for a catalogue short name delivers the CLI id from the shipped default mapping

#### Scenario: A declared map replaces the default whole

- **WHEN** an anthropic declaration carries its own `model_ids` block
- **THEN** every catalogue name resolves through that block, and a name the block does not map is delivered unchanged rather than falling back to the default entry

#### Scenario: An undeclared provider is never conjured from the default

- **WHEN** the configuration file is absent or does not declare the requested provider
- **THEN** resolution fails loudly naming the file and the fault, and the default id mapping plays no part in the failure

### Requirement: The mapping has one source

The Anthropic catalogue and its CLI-id mapping SHALL exist as one body of data. The
framework's model-name validation, the launch-plan translation, and the migration's
generated Anthropic declaration SHALL all read that same data, and the framework MUST NOT
maintain a second private copy of either the catalogue or the map.

#### Scenario: Re-pinning a short name changes every consumer together

- **WHEN** an entry in the shipped default mapping changes
- **THEN** the model-name validator, the launch plans, and a subsequent migration all deliver the new pinning with no second table to update
