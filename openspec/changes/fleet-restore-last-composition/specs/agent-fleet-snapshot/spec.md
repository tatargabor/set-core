## ADDED Requirements

### Requirement: The record states when the last discovery round happened

A write to the record SHALL stamp the document with the time of the round it just recorded —
the same instant it stamps on every entry that round saw. The stamp SHALL be written even
when the round saw no agents at all, because "the fleet was observed and was empty" is the
fact that distinguishes an empty composition from an unobserved one.

A document carrying no stamp — one written by an older build — SHALL be read as *the last
round is unknown*. It MUST NOT be inferred from the newest entry's last-seen time: that
would name a composition the record has no evidence for, and it would name it in the
direction that acts.

#### Scenario: Recording a round stamps the document with that round's time

- **WHEN** discovery reports agents and the record is written at time `T`
- **THEN** the document carries `T` as the time of the last round, and every entry that round saw carries `T` as its last-seen time

#### Scenario: A round that saw nothing still stamps the document

- **WHEN** a record write runs at time `T` with no agents reported
- **THEN** the document carries `T` as the time of the last round, and no entry's last-seen time is advanced

#### Scenario: A document with no stamp reports the last round as unknown

- **WHEN** a record written before this capability existed is read
- **THEN** the last round is reported as unknown, and it is not inferred from any entry's last-seen time

### Requirement: A read reports, per entry, whether it was in the last round

Reading a project's record SHALL report for each entry whether it belongs to the **last
round** — that is, whether it was still being seen when the fleet was last observed, which is
what "was open" means for a record that consults no live state.

An entry SHALL be reported as in the last round when its last-seen time is the document's
round stamp. When the stamp is absent, every entry's membership SHALL be reported as
**unknown**, never as `false`: a gap is not a zero, and this value decides what a restore
offers.

Entries outside the last round SHALL still be returned in full. Filtering them out would
make the record claim a smaller fleet than it holds, which is the failure this capability
already refuses for unresumable entries.

#### Scenario: Only the newest round is reported as the composition

- **WHEN** a project's record holds entries last seen in three different rounds and the newest round is the document's stamp
- **THEN** exactly the entries from the newest round are reported as in the last round, and every other entry is reported as not in it while still being returned

#### Scenario: A project that was not running when the fleet was last observed has an empty composition

- **WHEN** a project's record holds entries, none of which was seen in the round the document is stamped with
- **THEN** no entry is reported as in the last round, and the previous round is not reported as the composition in its place

#### Scenario: Membership is unknown when the document carries no stamp

- **WHEN** a record with no round stamp is read
- **THEN** every entry reports its last-round membership as unknown, and none reports `false`
