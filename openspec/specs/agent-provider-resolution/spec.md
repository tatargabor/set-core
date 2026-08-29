# agent-provider-resolution Specification

## Purpose
One resolver turning a project and a request into an environment, an argv and the provenance of every resolved value.

## IN SCOPE

- One resolver that every caller uses to turn a project and a request into the environment
  and command-line a provider needs
- The three precedence levels — machine default, project override, this start — and the
  hybrid merge across them
- The provenance the resolver reports: which level supplied each resolved field
- Every refusal the resolver makes, and the requirement that it makes them before any
  process is created
- Per-provider validation of model names, replacing a single global allowlist

## OUT OF SCOPE

- The file the resolver reads (`agent-provider-config`)
- Forking, holding or recording the agent process (`agent-provider-start`)
- The orchestration engine's role-based model chain, which is not consulted here
- Deciding WHICH provider a person should pick — the resolver answers what was asked for

## Requirements

### Requirement: One resolver serves every caller

The framework SHALL provide a single resolver that maps a project, an optionally requested
provider and an optionally requested model to the environment variables, the command-line
arguments and the provenance needed to launch an agent on that provider.

Every caller that launches an agent on a chosen provider SHALL obtain that environment from
this resolver. The framework MUST NOT contain a second implementation of the same mapping,
in any language.

#### Scenario: The command-line tool and the fleet produce the same environment

- **WHEN** the command-line runner and the fleet's agent owner resolve the same project, provider and model
- **THEN** both obtain the same environment variables and the same command-line arguments

#### Scenario: A measured launch parameter is stated once

- **WHEN** a provider's launch parameter changes
- **THEN** it changes in one place, and every caller's next launch reflects it

### Requirement: Precedence has three levels and the credential is inseparable from its endpoint

Resolution SHALL consider three levels, in increasing priority: the machine default, the
project override, and the values supplied with this start.

The merge across levels SHALL be hybrid:

- The credential and the endpoint it authenticates against SHALL be resolved together as
  one indivisible unit. A level that supplies either SHALL supply both, and the resolver
  MUST NOT combine a credential from one level with an endpoint from another.
- The model SHALL be resolved as an independent field, taking the value from the
  highest-priority level that supplies one.
- A machine-wide default model SHALL apply only when the resolved provider is the
  machine's default provider. A provider MAY declare its own default model, which
  is used when the resolved provider is not the default one. Where neither
  applies, resolution SHALL fail asking for a model and SHALL say that the
  machine default was not carried across, rather than reporting the machine
  default's model as unknown.

#### Scenario: A project overrides only the model

- **WHEN** a project override names a model but no credential, and the machine default supplies the credential and endpoint
- **THEN** the resolved model is the project's, and the resolved credential and endpoint are the machine default's, both taken from that one level

#### Scenario: A project override supplying a credential also supplies its endpoint

- **WHEN** a project override supplies a credential without the endpoint it belongs to
- **THEN** resolution fails naming the project and the incomplete pair, and no partial credential is used

#### Scenario: The start's request outranks both stored levels

- **WHEN** a start requests a provider and model, and both the machine default and the project override name different ones
- **THEN** the requested provider and model are resolved

#### Scenario: The machine default model is not carried to another provider

- **WHEN** a provider other than the machine default provider is resolved and no model is requested
- **THEN** that provider's own default model is used, and the machine default model is not

#### Scenario: A provider with no default of its own refuses and explains why

- **WHEN** a provider other than the machine default is resolved, no model is requested, and that provider declares no default model
- **THEN** resolution fails naming the provider whose model the machine default belongs to and listing the models that could be asked for

#### Scenario: A value the provider itself supplied is not attributed to the machine default

- **WHEN** a model comes from the resolved provider's own declaration
- **THEN** its provenance names the provider's level, distinct from the machine default's

### Requirement: The resolver reports where every resolved value came from

The resolver SHALL return, alongside the resolved values, the level that supplied each one.
That provenance SHALL be available to every caller and SHALL be reportable to a person
without requiring them to read the configuration to reconstruct it.

A resolution that used a credential other than the machine default SHALL be distinguishable
from one that did not, from the resolver's result alone.

#### Scenario: A run states which level decided

- **WHEN** an agent is launched on a resolved provider
- **THEN** the provider, the model and the level that supplied each are stated where the launch is reported

#### Scenario: A non-default credential is visible as such

- **WHEN** resolution takes the credential from a project override rather than the machine default
- **THEN** the result identifies the credential's level, without exposing the credential

### Requirement: Model names are validated against the resolved provider's own catalogue

A model name SHALL be validated against the catalogue of the provider it was resolved for.
The framework MUST NOT validate every model name against one global list.

A name that is valid for one provider and absent from another's catalogue SHALL be accepted
for the first and refused for the second.

#### Scenario: A provider's own model is accepted

- **WHEN** a model listed in a provider's catalogue is requested for that provider
- **THEN** resolution succeeds

#### Scenario: A model from another provider's catalogue is refused

- **WHEN** a model that appears only in another provider's catalogue is requested
- **THEN** resolution fails naming the model and the provider whose catalogue does not contain it

#### Scenario: The existing Anthropic names keep working unchanged

- **WHEN** a model name that the framework accepted before this change is requested for the Anthropic provider
- **THEN** it is accepted, and no previously valid name becomes invalid

### Requirement: Every refusal happens before a process is created, and never falls back

The resolver SHALL refuse, and the caller SHALL abandon the launch, when the resolved
provider has no credential, when the model is absent from the resolved provider's
catalogue, or when the model name carries a gateway prefix that the provider's endpoint
does not accept.

Each refusal SHALL occur before any process is forked or any scope, unit or handle is
allocated, so that the reported failure names the configuration fault rather than a
downstream symptom of it.

The framework MUST NOT, under any refusal, continue on a different provider than the one
requested.

#### Scenario: A missing credential stops the launch and names itself

- **WHEN** the resolved provider has no credential
- **THEN** resolution fails naming the provider and where its credential is expected, and no process is created

#### Scenario: A gateway-prefixed model name is caught before launch

- **WHEN** a requested model name carries a gateway prefix that the resolved provider's endpoint rejects
- **THEN** resolution fails naming the prefix and the accepted form, before any process is created

#### Scenario: A refusal is never a fallback

- **WHEN** resolution fails for a requested provider
- **THEN** no agent is started at all, and in particular none is started on a different provider

#### Scenario: The failure names the cause, not a later symptom

- **WHEN** a launch is abandoned because resolution refused
- **THEN** the reported reason is the configuration fault, and it is not reported as a process or scope that failed to become ready

### Requirement: Inherited credentials for other providers are removed from the launched environment

The environment the resolver produces SHALL remove any credential or endpoint for a
provider other than the resolved one that is present in the environment it inherits.

This removal SHALL happen for every resolved provider, including the default one, so that
an inherited value cannot silently redirect a launch.

#### Scenario: An inherited credential does not reach the agent

- **WHEN** the calling environment carries a credential or endpoint belonging to a provider other than the resolved one
- **THEN** the launched environment does not carry it

#### Scenario: The removal is unconditional across providers

- **WHEN** the resolved provider is the framework's default one
- **THEN** the removal still happens, and an inherited endpoint cannot redirect the launch
