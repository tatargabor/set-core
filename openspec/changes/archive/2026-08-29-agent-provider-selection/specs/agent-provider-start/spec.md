## IN SCOPE

- Asking for a provider and a model when starting an agent, as named fields
- Handing the resolved environment to the started process through the one point that
  survives the environment the framework strips
- A guard that the resolved environment actually reached the process
- Recording the provider, the model and the provenance durably enough to survive the
  lifetime of the process that started the agent
- Offering the catalogue to a surface without offering the credential
- Showing, where an agent is started and where it is listed, which provider and model it
  runs on and which level decided

## OUT OF SCOPE

- The configuration file (`agent-provider-config`) and the resolver
  (`agent-provider-resolution`)
- Restoring a recorded session (`agent-fleet-restore`)
- Starting an orchestration work unit, which is a separate route with its own body
- Choosing the model for an orchestration ROLE, which the engine's own chain answers

## ADDED Requirements

### Requirement: A start may name a provider and a model, and nothing more

The request that starts an agent SHALL accept an optional provider identifier and an
optional model name. Both SHALL be named fields drawn from the declared catalogue.

The request MUST NOT accept a command line, an argument list, or an environment mapping. A
provider or model the configuration does not declare SHALL be refused with the name that
was not recognised.

#### Scenario: A start names a provider and a model

- **WHEN** a start request names a declared provider and one of its models
- **THEN** the agent is started on that provider with that model

#### Scenario: A start naming neither takes the resolved default

- **WHEN** a start request names no provider and no model
- **THEN** resolution supplies both from the configuration, and the agent starts on the resolved values

#### Scenario: An undeclared name is refused by name

- **WHEN** a start request names a provider or model the configuration does not declare
- **THEN** the request is refused with an answer naming the unrecognised value, and no agent is started

#### Scenario: A free-form command is still not accepted

- **WHEN** a start request attempts to supply an argument list or an environment mapping
- **THEN** the request is rejected as malformed

### Requirement: The child environment is built by one named operation that a test holds

The construction of a started agent's environment SHALL be performed by a single named
operation. Any removal of inherited variables and any application of caller-supplied
variables SHALL happen inside it, and the caller-supplied variables SHALL be applied after
the removal.

That ordering SHALL be held by an automated test that fails when the removal is applied
after the caller's variables, rather than by comment or by adjacency alone.

#### Scenario: A caller-supplied variable that the removal targets still reaches the agent

- **WHEN** the resolved environment contains a variable whose name matches the class of variables the framework removes from an inherited environment
- **THEN** the started agent's environment contains that variable with the resolved value

#### Scenario: Reversing the order fails the suite

- **WHEN** the removal is applied after the caller-supplied variables instead of before
- **THEN** at least one test fails

### Requirement: A resolved variable that did not survive stops the start

Before a process is created, the framework SHALL verify that every environment variable the
resolver returned is present, with the resolved value, in the environment about to be used.

If any is absent or altered, the framework SHALL refuse the start and report which variable
was lost. It MUST NOT start the agent with an incomplete environment.

#### Scenario: A dropped variable is reported rather than tolerated

- **WHEN** a variable the resolver returned is absent from the environment about to be used
- **THEN** the start is refused naming that variable, and no process is created

#### Scenario: A complete environment starts normally

- **WHEN** every variable the resolver returned is present with its resolved value
- **THEN** the start proceeds

### Requirement: The provider an agent runs on outlives the process that started it

The provider, the model and the provenance of each SHALL be recorded at the moment of the
start, in a record that survives a restart of the service that started the agent.

The recording SHALL happen at the single point where a start is recorded, not at each
caller. For an agent already running whose provider was never recorded, the framework SHALL
report it as unrecorded rather than as running on a default.

#### Scenario: The provider is still known after the starting service restarts

- **WHEN** an agent is started on a named provider and the service that started it is restarted while the agent keeps running
- **THEN** the agent is still reported as running on that provider and model

#### Scenario: An unrecorded provider reads as unknown, not as the default

- **WHEN** an agent is listed whose provider was never recorded
- **THEN** it is reported as unrecorded, and it is not reported as running on the default provider

#### Scenario: One recording point covers every caller

- **WHEN** an agent is started through any caller that starts agents
- **THEN** its provider, model and provenance are recorded without that caller recording them itself

### Requirement: A surface receives the catalogue and never a credential

The framework SHALL offer, to a surface that starts agents, the declared providers, each
provider's model names, and whether a credential is configured for it.

A credential value MUST NOT appear in any response, log line, error message or diagnostic
the framework produces. A provider whose credential is not configured SHALL be offered as
unusable rather than omitted, so that a person sees why it cannot be chosen.

#### Scenario: The catalogue carries names and a presence flag

- **WHEN** a surface requests the provider catalogue
- **THEN** it receives the provider identifiers, their model names, and for each a statement of whether a credential is configured, and no credential value

#### Scenario: An unconfigured provider is shown as unusable

- **WHEN** a declared provider has no credential configured
- **THEN** it appears in the catalogue marked unusable, and starting on it is refused

#### Scenario: A diagnostic names the provider, not the secret

- **WHEN** a failure involving a credential is reported
- **THEN** the report names the provider and the endpoint, and does not contain the credential

### Requirement: The screen shows which provider an agent runs on and which level decided

The surface that starts agents SHALL offer a choice of provider and model, and SHALL show,
for the choice about to be made and for each running agent, the provider, the model, and
the precedence level that supplied each.

An agent running on a credential other than the machine default SHALL be visibly
distinguishable from one running on the default.

#### Scenario: The start offer states what would be used

- **WHEN** a person opens the offer to start an agent in a project with an override
- **THEN** the offered provider and model are the resolved ones, and the level that supplied each is shown

#### Scenario: A non-default credential is marked on the running agent

- **WHEN** an agent runs on a credential taken from a project override
- **THEN** the surface marks it as such where the agent is listed

#### Scenario: The screen is confirmed by looking at it

- **WHEN** the change is considered complete
- **THEN** the fleet start form and the agent list have been opened in a browser and inspected, or the inspection is recorded as not performed
