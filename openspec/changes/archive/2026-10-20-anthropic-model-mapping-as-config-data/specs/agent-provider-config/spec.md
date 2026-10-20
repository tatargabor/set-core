## ADDED Requirements

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

## MODIFIED Requirements

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
