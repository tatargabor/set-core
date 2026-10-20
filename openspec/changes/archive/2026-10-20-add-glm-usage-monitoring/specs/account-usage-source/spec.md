## ADDED Requirements

### Requirement: The measured set is the union of independent sources

The measurement SHALL be the union of every configured source, each discovered and read
inside its own failure boundary. One source failing to discover, or one account failing
to answer, SHALL remove no other source's accounts and no other account from the answer.
A source whose discovery raised SHALL keep whatever figures it last measured, and the
sources that did measure SHALL still stamp a fresh measurement time.

The failure boundary is per source, not per measurement. A machine whose provider
configuration is unreadable must not lose its Claude accounts because of it; that is the
same rule the poller already holds per account, held one level up.

#### Scenario: Two sources both answer

- **WHEN** two configured sources each discover accounts and measure them
- **THEN** the answer carries the union of both, under one measurement time

#### Scenario: One source fails to discover

- **WHEN** one source's discovery raises during a refresh
- **THEN** that source keeps its previously measured accounts, the failure is recorded,
  the other sources' accounts are measured normally, and the answer carries a fresh
  measurement time

## MODIFIED Requirements

### Requirement: Severity and scoped windows come from upstream, not from a local threshold

The framework SHALL carry the severity the upstream states for a window, and SHALL carry any
scoped window the upstream reports — a window that applies to one model or surface rather than to
the account as a whole — naming that scope. The framework SHALL NOT invent a scoped window, and
SHALL NOT overwrite an upstream severity with a locally computed band.

A source whose upstream states no severity at all MAY have that source's windows banded at
measurement, in the one named place that source's own specification defines — never per caller,
and never on the screen. A severity an upstream did state SHALL reach the caller exactly as
stated: the local band applies only where there is nothing to prefer, and never as a second
opinion over an upstream's own.

A threshold chosen here is a second opinion about somebody else's limit, and it drifts silently
when theirs moves. Measured 2026-08-27: a 96 % weekly window arrived already labelled critical,
and beside it a model-scoped window at 2 %.

#### Scenario: The upstream labels a window

- **WHEN** a window arrives carrying a severity
- **THEN** that severity is what the record reports, unmodified

#### Scenario: A model-scoped window is present

- **WHEN** the upstream reports a window scoped to a named model
- **THEN** it is carried with its scope name, kept apart from the account-wide window

#### Scenario: No scoped window is reported

- **WHEN** the upstream reports no scoped window
- **THEN** none is reported, and no scope is derived from the account-wide figures

#### Scenario: A source whose upstream states no severity

- **WHEN** a source's upstream states no severity for its windows, and that source's own
  specification defines a measurement-time band
- **THEN** the band is applied in that one place, and no stated severity anywhere in the
  measurement is overwritten by it
