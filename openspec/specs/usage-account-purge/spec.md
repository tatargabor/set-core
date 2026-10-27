# usage-account-purge Specification

## Purpose
TBD - created by archiving change add-usage-account-purge. Update Purpose after archive.

## Requirements

### Requirement: An account is removed only from the dead, and only by name

The framework SHALL remove a usage account from its machine's credential stores when a
request names that account by kind and name, and SHALL refuse any named account whose
current measurement is not unreachable. A screen that has gone stale MUST NOT be able to
delete a healthy account's credential: the guard is enforced where the stores are
written, not only where the button is drawn.

The refusal SHALL name the account and the reason, and SHALL remove nothing.

#### Scenario: A dead account is purged

- **WHEN** a request names an account whose current measurement is unreachable
- **THEN** that account's stored credential is removed from its store, and the answer
  reports the removal by kind and name

#### Scenario: A healthy account is named

- **WHEN** a request names an account whose current measurement is measured or unmeasured
- **THEN** the account is refused and named in the answer, and its store is untouched

#### Scenario: An account the measurement does not know

- **WHEN** a request names a kind and name the current measurement carries no record of
- **THEN** the account is refused and named in the answer, and no store is touched

### Requirement: Each store keeps its own removal rules

Removal SHALL follow the rules of the store the account lives in. The browser session
store SHALL drop the matching entries and write the survivors back atomically, always in
the current multi-account shape, with the file's owner-only permissions preserved. The
CLI OAuth store SHALL remove through the same rules its own manager enforces — the last
account is refused, and an active account that is removed has the active role moved to a
survivor. An entry that does not exist SHALL be reported as not found, not as removed.

A removal request naming several accounts SHALL be applied per account: one account's
refusal SHALL not stop the others, and the answer SHALL separate what was removed from
what was refused.

#### Scenario: The last CLI account is named

- **WHEN** a request names the only remaining CLI OAuth account, and it is unreachable
- **THEN** the removal is refused under the store's last-account rule, and the answer
  reports that refusal

#### Scenario: The active CLI account is named

- **WHEN** a request removes the active CLI OAuth account and others remain
- **THEN** the active role moves to a survivor, and the answer reports both the removal
  and the account that became active

#### Scenario: A mixed request

- **WHEN** a request names several accounts, some removable and some refused
- **THEN** every removable one is removed, every refused one is named with its reason,
  and neither list is implied by the other

### Requirement: A provider credential is refused, not removed

An account whose credential lives in the provider configuration — kind `glm` — SHALL be
refused with an answer that says where that credential is actually managed. The provider
configuration is a hand-edited data file by design; a purge endpoint that edited it would
turn a deliberate configuration act into a button press.

#### Scenario: A GLM account is named

- **WHEN** a request names an account of kind `glm`
- **THEN** the removal is refused, the answer names the provider configuration as the
  place to edit, and `providers.json` is untouched

### Requirement: No credential leaves the stores through the answer

The purge answer and every log line it produces SHALL carry kinds, names, counts, and
reasons — and no credential. A removal is exactly the moment a secret is in hand, which
is exactly when the rule is easiest to break and most costly to break.

#### Scenario: The answer is inspected

- **WHEN** a purge completes in any combination of removals and refusals
- **THEN** no field of the answer and no line logged by it carries any removed or
  refused account's credential
