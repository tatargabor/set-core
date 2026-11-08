## IN SCOPE
- Scanning the local browser profiles for Claude session cookies from the dashboard's process
- Merging the result into the browser session store, and measuring again at once
- Reading the browser's cookie password from the keyring in a way one broken item cannot defeat

## OUT OF SCOPE
- A scheduled or automatic rescan
- The CLI account store, which the CLI keeps fresh itself
- Removing accounts: the existing purge does that

## ADDED Requirements

### Requirement: A rescan replaces scanned sessions and keeps manual ones

`POST /api/usage/accounts/rescan` SHALL scan every local browser profile for a Claude session
cookie. It SHALL validate each cookie, and SHALL then write the browser session store: entries
entered by hand are kept, and scanned entries are replaced by the scan's result. The store SHALL
be written atomically with owner-only permissions. A scan that found no session, or could not run,
SHALL NOT write the store.

#### Scenario: Fresh cookies replace expired ones

- **WHEN** the store holds a scanned session whose cookie expired and the browser holds a fresh one
- **THEN** after the rescan the store holds the fresh cookie under the same name, mode 0600

#### Scenario: A manual entry survives

- **WHEN** the store holds an entry with `source: manual`
- **THEN** it is still there after the rescan

#### Scenario: Nothing found

- **WHEN** the scan finds no session or cannot run
- **THEN** the store is unchanged and the answer says why

### Requirement: The rescan measures again and answers without secrets

After a write, the route SHALL take one measurement at once. It SHALL answer with the names of
the sessions found and the new snapshot. No session key SHALL appear in the answer or in a log
line. A second rescan while one is running SHALL be refused with 409, never queued.

#### Scenario: The answer

- **WHEN** a rescan finds two sessions
- **THEN** the answer names both and carries the fresh snapshot, and contains no cookie value

#### Scenario: Pressed twice

- **WHEN** a rescan is requested while another is running
- **THEN** the second answers 409 and starts nothing

### Requirement: The keyring password is found despite a broken item

The scan SHALL look up the browser's cookie password by its attribute (`application=chrome`)
before walking the keyring. A walk SHALL read each item inside its own failure boundary, so one
dangling item cannot make the lookup fail.

#### Scenario: A dangling keyring item

- **WHEN** the login collection holds an item the secret service cannot load
- **THEN** the password is still found by the attribute lookup and the cookies decrypt
