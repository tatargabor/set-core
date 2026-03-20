# Design: Enrich Digest Domains Tab

## Context

The web dashboard has two overlapping tabs for requirement tracking: Requirements (ProgressView) and Digest (DigestView). The Digest tab already contains richer data (47 requirements with domains, AC items, coverage, dependencies, ambiguities) but the Domains sub-tab only renders 1-sentence markdown summaries. The Requirements tab duplicates domain-grouped requirement views using a separate API endpoint.

All enrichment data is already available in the `/api/{project}/digest` response — no backend changes needed.

## Goals / Non-Goals

**Goals:**
- Single source of truth for requirement/domain tracking (Digest tab)
- Rich domain cards that cross-reference all available digest data
- Preserve the Dependency Tree visualization

**Non-Goals:**
- Changing the digest generation or LLM prompts
- Adding new API endpoints
- Changing the data model

## Decisions

### 1. Enrich DomainsPanel with existing props
**Decision:** Pass `reqs`, `coverage`, `dependencies`, and `ambiguities` from DigestView to DomainsPanel as props.
**Rationale:** The DigestView already fetches and parses all this data. The DomainsPanel currently only receives `domains` (the markdown dict). Adding props is simpler than a separate fetch.

### 2. Domain card layout — sections in vertical stack
**Decision:** Each domain card has 5 collapsible sections: Summary+Progress, Requirements, AC Coverage, Ambiguities, Dependencies+Sources.
**Rationale:** Vertical stack with collapsible sections keeps the card scannable. Users typically care about progress first, details second.
**Alternative considered:** Tabbed sub-views per domain — rejected because it adds navigation depth without benefit.

### 3. Sidebar mini-bars — inline with domain names
**Decision:** Add a small (w-16) inline progress bar and "N/M" count next to each domain name in the sidebar.
**Rationale:** Gives instant overview without clicking. The sidebar already has room for this.

### 4. Move DependencyTree, don't rewrite
**Decision:** Import and reuse the DependencyTree component from ProgressView, placing it in a new "Dep Tree" sub-tab within DigestView. After confirming it works, delete ProgressView entirely.
**Rationale:** The DependencyTree is well-tested and works with change-level data from the requirements API. No need to rewrite. The DigestView can fetch requirements data for just this sub-tab.

### 5. Cross-domain dependency computation
**Decision:** Compute domain-level edges by mapping requirement IDs to domains, then grouping edges by (from_domain, to_domain).
**Rationale:** The dependencies.json has requirement-level edges (REQ-CART-001 → REQ-CAT-003). Each REQ ID encodes its domain in the prefix (REQ-{DOMAIN}-{NNN}). Simple string parsing gives domain membership.

## Risks / Trade-offs

- [Risk] ProgressView has a `getRequirements()` API fallback for when digest doesn't exist → Mitigation: The Dep Tree sub-tab can lazy-load requirements data only when selected, and show "No data" gracefully when neither exists.
- [Risk] Removing Requirements tab breaks muscle memory → Mitigation: The Digest tab is in the same position and the Dep Tree sub-tab preserves the unique view that Requirements offered.
