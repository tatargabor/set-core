## IN SCOPE

- Discovering which accounts this machine has credentials for, and how each authenticates
- Reading each account's rolling usage windows from the upstream account API
- Distinguishing *not configured*, *unreachable*, and *reachable but unmeasured* from one another
- Carrying the upstream severity and the per-model scoped windows without reinterpreting them
- Polling on a schedule and serving a cached answer that names when it was measured

## OUT OF SCOPE

- Estimating usage from local transcript files when the upstream did not answer: an estimate and
  a measurement render identically, and the reader cannot tell them apart afterwards
- Any write: no credential is created, refreshed, rotated, or repaired here
- Cost in currency, billing, or extra-usage credits
- Per-agent or per-session attribution of consumption (see `fleet-usage-bars` for why)
- The Control Center's own rendering, which keeps every requirement it has

## ADDED Requirements

### Requirement: Accounts are discovered from the machine's configuration, with their auth kind

The framework SHALL discover usage-capable accounts from the credential stores this machine
already keeps, and SHALL carry, for each, the authentication kind it requires — a browser session
cookie or an OAuth bearer token. An account whose stored credential is missing or empty SHALL NOT
be reported as an account.

The kind is part of the record rather than a lookup at call time because the two kinds fail
differently: a scanned browser cookie expires without notice, and a token does not. A caller that
cannot see which kind it holds cannot say which failure it is looking at.

#### Scenario: Both credential stores hold accounts

- **WHEN** the machine holds both browser-derived session keys and OAuth-token accounts
- **THEN** every one of them is reported, each naming its own authentication kind

#### Scenario: A store holds an entry with no usable credential

- **WHEN** an entry carries no session key, or no access token
- **THEN** that entry is not reported as an account, and its presence does not make the list longer

#### Scenario: No credentials at all

- **WHEN** neither store exists or both are empty
- **THEN** the answer is an empty account list, which is distinct from an account that could not
  be measured

### Requirement: Usage is read from the upstream account API, never estimated

For each discovered account the framework SHALL read the rolling usage windows from the upstream
account API using that account's own credential, and SHALL report only what that answer contains.
Where the upstream did not answer, the framework SHALL report the account as unreachable and
SHALL NOT substitute a locally computed figure.

A locally estimated percentage and a measured one occupy the same bar, in the same place, with no
way for the reader to tell them apart once drawn. The estimate's error is also one-directional in
the dangerous way: it is computed against a configured limit guess, so it reads low exactly when
the real quota is nearly spent.

#### Scenario: The upstream answers

- **WHEN** the account API returns the usage document for an account's organization
- **THEN** the windows reported are the ones that document carries

#### Scenario: Every transport fails

- **WHEN** no transport reaches the upstream for an account
- **THEN** that account is reported unreachable, with no window figures attached

### Requirement: A reachable account with no measured window is not a zero

Where the upstream answers for an account but carries no figure for a window, the framework SHALL
report that window as unmeasured, and SHALL NOT report it as zero, absent, or full.

This is not hypothetical. Measured 2026-08-27 against the live API, one of three reachable
accounts answered `200` with both its 5-hour and 7-day windows null. Reported as zero it says
"nothing consumed, start whatever you like"; the honest answer is that nobody knows.

#### Scenario: A window the upstream did not fill

- **WHEN** the usage document carries the account but its window object is null
- **THEN** that window is marked unmeasured, distinguishably from a window measured at zero

#### Scenario: One window measured and one not

- **WHEN** an account's 5-hour window carries a figure and its 7-day window does not
- **THEN** the measured window is reported with its figure and the other is marked unmeasured

### Requirement: Severity and scoped windows come from upstream, not from a local threshold

The framework SHALL carry the severity the upstream states for a window, and SHALL carry any
scoped window the upstream reports — a window that applies to one model or surface rather than to
the account as a whole — naming that scope. The framework SHALL NOT invent a scoped window, and
SHALL NOT overwrite an upstream severity with a locally computed band.

A threshold chosen here is a second opinion about somebody else's limit, and it drifts silently
when theirs moves. Measured 2026-08-27: a 96 % weekly window arrived already labelled critical,
and beside it a model-scoped window at 2 %.

#### Scenario: The upstream labels a window

- **WHEN** a window arrives carrying a severity
- **THEN** that severity is what the record reports

#### Scenario: A model-scoped window is present

- **WHEN** the upstream reports a window scoped to a named model
- **THEN** it is carried with its scope name, kept apart from the account-wide window

#### Scenario: No scoped window is reported

- **WHEN** the upstream reports no scoped window
- **THEN** none is reported, and no scope is derived from the account-wide figures

### Requirement: The measurement is polled, and every answer says when it was taken

The framework SHALL refresh account usage on its own schedule and SHALL serve callers from the
last completed measurement. A caller SHALL NOT be able to cause an upstream request by reading.
Every answer SHALL carry the time the measurement was taken.

Reading is a screen refresh; measuring is a rate-limited network call against somebody else's
service, and the two must not be the same act. The timestamp is what makes a stale answer
readable rather than merely wrong — a screen that cannot say how old its numbers are is
indistinguishable from one that is up to date.

#### Scenario: Two reads between two polls

- **WHEN** a caller reads twice within one polling interval
- **THEN** both reads are answered from the same measurement, and no upstream request is made

#### Scenario: A poll fails after a successful one

- **WHEN** a refresh fails and an earlier measurement exists
- **THEN** the earlier measurement is still served, with its own timestamp, rather than being
  replaced by an error

### Requirement: No credential leaves the measuring process

The record the framework hands to any caller SHALL carry no session key, no bearer token, and no
value derived from one. Log output about this subsystem SHALL name the shape of what it handled —
the account count, the kind, the outcome — and never the credential itself.

The boundary is persistence and transport, not naming: these credentials grant access to a live
account, and a browser payload, a debug dump, and a log line all leave the process.

#### Scenario: The answer is inspected

- **WHEN** an account's usage record is serialised for a caller
- **THEN** no field of it contains the credential that was used to obtain it

#### Scenario: An account fails to authenticate

- **WHEN** a request is rejected for an account
- **THEN** the failure is reported and logged without the credential appearing in either
