## IN SCOPE

- Discovering the GLM account from the machine's provider credential, and being
  absent — not unreachable — when none is configured
- Reading the account's rolling quota windows from the provider's monitor endpoint,
  authenticated with the credential exactly as the endpoint requires
- Window group and length derived from the upstream's own unit and number
- Reset times carried in epoch milliseconds by the upstream, reported as ISO UTC
- The one local severity band, for a source that states no severity of its own
- The credential never leaving the measuring process

## OUT OF SCOPE

- Per-model or per-tool usage statistics the same upstream can also answer — the
  client is shaped so they can be added, but they are not read yet
- Cost in currency (the GLM plan is credit-denominated, and no rate table is added)
- Any write to the provider configuration: adding, rotating or removing a GLM
  credential stays a hand edit of `providers.json`
- The poller's schedule and snapshot shape — owned by `account-usage-source`
- The strip's rendering — owned by `fleet-usage-bars`

## ADDED Requirements

### Requirement: The GLM account is discovered from the machine's provider credential, and absent when there is none

The framework SHALL discover at most one GLM account, from the credential the machine's
provider configuration declares for the `glm` provider, and SHALL carry it with kind `glm`.
When no provider configuration is readable, or the configuration declares no `glm` provider,
or that provider carries no usable credential, the source SHALL contribute no account — a
state that is distinct from an account that was discovered and could not be measured.

An entry with no usable credential is not an account: reporting it would make the list
longer without making anything measurable. A provider configuration that cannot be read is
likewise not an account, and it MUST NOT take the other sources' accounts down with it.

#### Scenario: A configured GLM credential is discovered with its kind

- **WHEN** the provider configuration declares a `glm` provider carrying a usable credential
- **THEN** exactly one account of kind `glm` is contributed to the measurement

#### Scenario: No GLM provider is configured

- **WHEN** the machine keeps no `glm` provider, or that provider carries no usable credential
- **THEN** no GLM account is contributed, and the answer carries no unreachable GLM row

#### Scenario: The provider configuration cannot be read

- **WHEN** reading the provider configuration raises — the file is absent, malformed, or
  its permissions are wrong, including for a provider unrelated to GLM
- **THEN** the GLM source contributes no account, the failure is recorded, and the other
  sources' accounts are unaffected

### Requirement: Usage is read from the provider's monitor quota endpoint with the credential as given

The framework SHALL read the account's rolling quota windows from the monitor quota
endpoint on the host the credential's base URL names, and SHALL authenticate with the
credential in the exact form that endpoint requires — today an `Authorization` header
carrying the raw token. The authentication form is a measured property of the upstream,
not a style choice: a header that looks more conventional but prefixes the token changes
what the endpoint answers.

An answer that is rejected, names failure, or is not the expected document SHALL make the
account unreachable with no figures. An answer carrying no window SHALL leave the account
unmeasured. Neither state SHALL be reported as the other, and neither as zero.

#### Scenario: The endpoint answers with quota windows

- **WHEN** the monitor quota endpoint answers with a document carrying limits
- **THEN** those limits are reported as the account's windows, with nothing synthesised
  beyond what the document states

#### Scenario: The endpoint rejects the read

- **WHEN** the endpoint answers with a rejection, a failure marker, or no usable document
- **THEN** the account is reported unreachable with no figures, and any earlier figures
  stay on screen marked with their age

### Requirement: Window group and length come from the upstream's own unit and number

Each window's group SHALL follow from the upstream's own unit and number — a five-hour
window SHALL be grouped `session`, a weekly one `weekly` — and the window's length SHALL
be computed from that same unit and number rather than from a fixed table. A limit whose
unit or number the framework does not recognise SHALL still be reported, keeping its own
upstream type as its kind, with no window length: a window whose length is unknown SHALL
draw no elapsed stripe rather than a guessed one.

The upstream's limit types are read verbatim. A type the framework has never seen SHALL
be kept as its own kind and counted by no rule that names a type it does not know.

#### Scenario: The five-hour and weekly limits answer

- **WHEN** the document carries a five-hour limit and a weekly limit
- **THEN** the first is reported as a `session` window of its stated length and the second
  as a `weekly` window of one week

#### Scenario: An unknown unit arrives

- **WHEN** a limit carries a unit or number the framework does not map to a known group
- **THEN** the window is still reported, its length is reported as unknown, and no elapsed
  fraction is computed for it

#### Scenario: A limit type the framework has never seen

- **WHEN** the document carries a limit whose type is not one the framework names
- **THEN** that type is carried verbatim as the window's kind, and the window is not dropped

### Requirement: An epoch-millisecond reset time is reported as ISO UTC

The upstream states reset times as epoch milliseconds. The framework SHALL convert them to
ISO UTC before they reach any caller, and SHALL report a value it cannot parse as absent
rather than guessing a unit or an epoch.

#### Scenario: A millisecond reset time is reported

- **WHEN** a limit carries a plausible epoch-millisecond reset time
- **THEN** the window reports that instant as ISO UTC

#### Scenario: A reset time that cannot be parsed

- **WHEN** a limit carries a reset time that is not a usable number
- **THEN** the window's reset time is absent, not a guessed value

### Requirement: Severity is banded here for this source, in one named place, because the upstream states none

This source's upstream states no severity. The framework SHALL band this source's windows
itself — warning at seventy per cent, critical at ninety — and SHALL do so in exactly one
named place: the client that measures this source. The band SHALL never be applied to a
window whose upstream stated a severity, and SHALL never be computed on the screen.

These are set-core's own thresholds, because nobody else's exist to prefer. The single
place is the guard against them spreading: any rule that needs a GLM severity takes the
one the measurement carries.

#### Scenario: A window crosses the critical threshold

- **WHEN** a window's measured percentage reaches ninety
- **THEN** the measurement reports that window's severity as critical

#### Scenario: A window crosses the warning threshold

- **WHEN** a window's measured percentage reaches seventy but not ninety
- **THEN** the measurement reports that window's severity as warning

#### Scenario: A window without a percentage

- **WHEN** a limit carries no percentage
- **THEN** the window is unmeasured, carries no severity, and is never reported as a
  measured zero

### Requirement: The credential does not leave the measuring process

The GLM credential SHALL appear in no repr, no log line, and no serialised record the
measurement produces — the same rule the other sources are held to, and for the same
reason: a debug line is a leak path that needs no decision to happen.

#### Scenario: The record is serialised

- **WHEN** an account's usage record is serialised for a caller
- **THEN** no field of that record carries the credential

#### Scenario: A failure is logged

- **WHEN** the measurement logs a failure against the GLM account
- **THEN** the log line names the failure and no part of the credential
