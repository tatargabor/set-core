# Upstream Model Watch

## IN SCOPE

- Reading Anthropic's public model overview page, with no credential
- Comparing its model ids with the ids set-core ships
- Comparing the names set-core ships with the machine's declared `anthropic` catalogue
- A three-state verdict — `current`, `behind`, `unknown` — with the reason for each gap
- A 24 h cache of the fetched ids, and a way to bypass it
- Reporting it on the CLI, a read-only API route, and the "Start an agent" dialog

## OUT OF SCOPE

- Changing any configuration or code: the check advises, a person updates set-core
- Providers other than `anthropic` (e.g. `glm`)
- Using the models API, or any credential, including the agent CLI's own login
- Deciding which short name should resolve to which id
- Periodic background polling or push notifications

## ADDED Requirements

### Requirement: The upstream list is read from the public overview's id rows only
The system SHALL fetch Anthropic's public model overview page without sending any
credential, and SHALL take model ids only from the overview table rows labelled
"Claude API ID" and "Claude API alias". It SHALL NOT collect `claude-…` strings from the
rest of the page, because prose, link slugs and other platforms' ids are not model ids.

#### Scenario: Ids come from the two id rows
- **WHEN** the page holds a "Claude API ID" row with `claude-sonnet-5-5` and a link whose URL contains `claude-prompting-best-practices`
- **THEN** the parsed ids include `claude-sonnet-5-5` and do not include `claude-prompting-best-practices`

#### Scenario: Other platforms' ids are ignored
- **WHEN** the page holds an "Amazon Bedrock ID" row with `anthropic.claude-opus-5-5`
- **THEN** no id is taken from that row

### Requirement: A check that could not measure reports unknown, never current
The system SHALL report the verdict `unknown`, together with the reason, when the fetch
fails, times out, returns a non-success status, or when the page yields zero ids.
The system SHALL NOT report `current` unless at least one upstream id was parsed.

#### Scenario: Network failure
- **WHEN** the fetch raises a connection error
- **THEN** the verdict is `unknown` and the reason names the failure

#### Scenario: The page changed shape
- **WHEN** the page is fetched successfully but contains no "Claude API ID" row
- **THEN** the verdict is `unknown` with a reason saying no ids were found, not `current`

### Requirement: An upstream id set-core does not ship is reported as behind
The system SHALL treat an upstream id as covered when it, or its alias from the same
column, equals a value of the shipped id mapping (ignoring a `[1m]` suffix), or when its
family (`opus`, `sonnet`, `haiku`, `fable`) is a shipped pass-through name with no id
mapping. Every other upstream id SHALL make the verdict `behind`, and the report SHALL
name the id and the id that the family's short name currently resolves to.

#### Scenario: A new Sonnet is published
- **WHEN** upstream lists `claude-sonnet-5-5` and the shipped mapping has `sonnet` → `claude-sonnet-4-6` and no value `claude-sonnet-5-5`
- **THEN** the verdict is `behind` and the report names `claude-sonnet-5-5` and says `sonnet` resolves to `claude-sonnet-4-6`

#### Scenario: A pass-through family is covered
- **WHEN** upstream lists `claude-fable-5-1` and `fable` is a shipped name with no id mapping
- **THEN** `claude-fable-5-1` is not reported

#### Scenario: A dated id matched through its alias
- **WHEN** upstream's API ID is `claude-haiku-4-5-20251001`, its alias is `claude-haiku-4-5`, and the shipped mapping contains `claude-haiku-4-5-20251001`
- **THEN** the haiku column is not reported

### Requirement: A shipped name missing from the machine catalogue is reported
The system SHALL compare the shipped Anthropic names with the models declared for the
`anthropic` provider in the machine's provider configuration. Each shipped name that is not
declared SHALL make the verdict `behind`, and SHALL be reported with advice to add it to that
configuration file. If the configuration declares no `anthropic` provider, this comparison
SHALL be skipped, and the report SHALL say it was skipped.

#### Scenario: A machine file older than the shipped names
- **WHEN** the machine's anthropic catalogue lacks `opus-5-5` and the shipped names contain it
- **THEN** the verdict is `behind` and `opus-5-5` is listed under the machine catalogue with the file's path

### Requirement: The fetched list is cached for a day and can be refreshed
The system SHALL store the parsed upstream ids with their fetch time in the user's cache
directory, outside every repository, and SHALL reuse them for 24 hours without fetching.
A refresh request SHALL fetch regardless of the cache's age. An `unknown` result SHALL NOT
overwrite a cached successful list, and the report SHALL say how old the list it used is.

#### Scenario: A fresh cache is reused
- **WHEN** the cache holds a list fetched 2 hours ago and no refresh is requested
- **THEN** no fetch is made and the report shows the cached fetch time

#### Scenario: A failed refresh keeps the last good list
- **WHEN** a refresh fetch fails while the cache holds a list from yesterday
- **THEN** the verdict is `unknown` and the cache still holds yesterday's list

### Requirement: The check only advises
The system SHALL NOT write to the provider configuration, to any set-core source file, or to
any repository as a result of the check. Its only write SHALL be its own cache file.

#### Scenario: A behind verdict changes nothing
- **WHEN** the verdict is `behind`
- **THEN** the provider configuration file's bytes are unchanged

### Requirement: The verdict is visible on the CLI, the API, and the start dialog
`set-providers upstream` SHALL print the verdict, each gap, and the advice. It SHALL exit
with 0 for `current`, 1 for `behind` and 2 for `unknown`, and SHALL accept `--refresh`
and `--json`. `GET /api/fleet/models/upstream` SHALL return the same report as JSON. The
"Start an agent" dialog SHALL show a notice when the verdict is `behind` or `unknown`, and
SHALL show nothing extra when it is `current`. A failure to load the report SHALL NOT
block starting an agent.

#### Scenario: Exit codes
- **WHEN** `set-providers upstream` runs with a behind verdict
- **THEN** it exits 1 and prints the missing id and the advice to update set-core

#### Scenario: The dialog names the gap
- **WHEN** the dialog opens and the report is `behind` because of `claude-sonnet-5-5`
- **THEN** the dialog shows a notice naming `claude-sonnet-5-5` and saying set-core needs updating

#### Scenario: The report route is down
- **WHEN** the upstream route answers 500
- **THEN** the dialog still offers every model and the start button, and says the model list could not be checked
