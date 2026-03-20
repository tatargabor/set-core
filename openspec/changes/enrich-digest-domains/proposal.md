# Proposal: Enrich Digest Domains Tab

## Why

The Digest tab's Domains sub-tab currently shows a single sentence per domain — no progress, no requirement breakdown, no cross-domain dependencies. Meanwhile, the standalone Requirements tab duplicates most of the Digest's Overview/Reqs functionality using a different data source. This creates confusion about which tab to use and wastes dashboard real estate.

## What Changes

- **Enrich the DomainsPanel** component to display per-domain progress bars, requirement lists with coverage status, acceptance criteria counts, ambiguity warnings, cross-domain dependency links, and source file references — all derived from data already present in the digest API response
- **Add progress mini-bars to the domain sidebar** so users can see at a glance which domains are complete, in-progress, or pending
- **Remove the standalone Requirements tab** (ProgressView) since the enriched Digest tab subsumes its functionality
- **Move the Dependency Tree view** into the Digest tab as a new sub-tab, preserving the change-level dependency visualization

## Capabilities

### New Capabilities
- `digest-domain-enrichment`: Rich domain cards with progress, requirements, ambiguities, dependencies, and sources

### Modified Capabilities
- (none — no existing spec-level behavior changes, this is a new UI feature)

## Impact

- **Frontend only**: `web/src/components/DigestView.tsx`, `web/src/components/ProgressView.tsx`, `web/src/pages/Dashboard.tsx`
- **No backend changes**: All data already exists in the `/api/{project}/digest` response (requirements, coverage, dependencies, ambiguities)
- **No API changes**: No new endpoints needed
- **Removes code**: `ProgressView.tsx` can be deleted entirely, reducing ~530 lines of duplicated logic
