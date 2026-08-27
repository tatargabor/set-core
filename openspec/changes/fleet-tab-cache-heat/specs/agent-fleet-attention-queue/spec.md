## MODIFIED Requirements

### Requirement: The queue is ordered by freshness of the blockage, not by arrival

Within a project, the queue SHALL order items by the money a prompt answer still saves: for an
agent whose prompt cache is still live, the size of that cache multiplied by the difference
between the cache-rewrite and cache-read prices; for an agent whose cache has expired, zero. The
framework SHALL NOT order by how long an item has been waiting.

Where no cache state was measured, the framework SHALL fall back to ordering by how recently the
agent became blocked, most recent first, and SHALL rank an unmeasured item against measured ones
by that fallback alone rather than by an assumed size or age.

This inverts the usual fairness rule and it is deliberate. The reason is a cost, not a preference:
an agent answered while its prompt cache is still warm resumes from that cache, and one answered
long after re-reads its whole context. Freshness was the proxy for that cost while no measurement
existed; now one does, and the proxy is wrong in two ways worth naming. It cannot see the STAKE —
two agents blocked for the same ten minutes may hold caches that differ more than tenfold — and it
cannot see the THRESHOLD: past the cache lifetime there is nothing left to save, so a long-blocked
agent's ordering is no longer a cost question at all.

The price is starvation, and the next requirement is what pays it.

#### Scenario: A larger stake outranks an equally fresh smaller one

- **WHEN** two agents became blocked at the same moment and both caches are still live, but one
  holds several times the tokens of the other
- **THEN** the agent holding the larger cache is presented first

#### Scenario: An expired cache carries no urgency

- **WHEN** one agent's cache lifetime has elapsed and another's has not
- **THEN** the agent whose cache is still live is presented first, whatever their blockage times

#### Scenario: A fresh blockage outranks an old one
- **WHEN** one agent became blocked two minutes ago and another forty minutes ago, and neither
  agent's cache state could be measured
- **THEN** the two-minute-old blockage is presented first

#### Scenario: A project is exhausted before the next one is entered
- **WHEN** more than one project holds queued items the reader has not seen yet
- **THEN** every unseen item of the presented item's project is offered before an unseen item of
  another project

Project exhaustion ranks the items the reader has NOT seen. It does not rescue an item the reader
was already shown and did not deal with — that item is demoted past every project, which is what
makes deferral able to leave the project at all.
