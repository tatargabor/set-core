# Battle View Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Space Invaders style visualization of orchestration change pipeline
- Spatial mapping of change status to screen zones (orbit/atmosphere/ground)
- Animated transitions between change states
- Ralph character reflecting agent activity
- Live event feed with narrated status updates
- Responsive layout (desktop + mobile via Tailscale)
- Tab integration in existing dashboard tab bar

### Out of scope
- User-controlled gameplay (Ralph acts autonomously based on data)
- Sound effects or audio
- Backend API changes (uses existing state + WebSocket)
- Persistent leaderboards or server-side score storage

## Requirements

### Requirement: Spatial Zone Layout
The battle view SHALL render three horizontal zones representing pipeline stages:
- **Orbit** (top) — pending/queued changes shown as invader sprites
- **Atmosphere** (middle) — running/verifying changes shown as descending ships with progress
- **Ground** (bottom) — completed/merged changes shown as landed items

#### Scenario: All zones populated
- **WHEN** an orchestration has changes in pending, running, and done states
- **THEN** each change MUST appear in the zone matching its current status

#### Scenario: Empty orchestration
- **WHEN** no orchestration is active or state has no changes
- **THEN** the battle view MUST show an idle screen with Ralph sleeping

### Requirement: Change-to-Sprite Mapping
Each change status SHALL map to a distinct visual representation:

| Status | Sprite | Zone |
|--------|--------|------|
| pending | 👾 invader | Orbit |
| dispatched | 🛸 entering atmosphere | Atmosphere (top) |
| running/implementing | 🛸 with progress bar + tok/s | Atmosphere |
| verifying | 🔍 scanner beam | Atmosphere (low) |
| failed | 💥 explosion → 🔧 rebuild | Atmosphere |
| done/merged/completed | ✅ landed flag | Ground |
| stalled | ⚠️ blinking yellow | Atmosphere |

#### Scenario: Change transitions from pending to running
- **WHEN** a change status changes from `pending` to `running`
- **THEN** its sprite MUST animate from the orbit zone downward into the atmosphere zone

#### Scenario: Change fails
- **WHEN** a change status becomes `failed`
- **THEN** the sprite MUST play an explosion animation, then show a rebuild animation if retry count < max

#### Scenario: Change completes
- **WHEN** a change status becomes `done`, `merged`, or `completed`
- **THEN** the sprite MUST animate a landing sequence to the ground zone with a brief celebration effect

### Requirement: Sprite Sizing by Complexity
Change sprites SHALL vary in size based on the `complexity` field:
- `S` — small sprite (1x)
- `M` — normal sprite (1.5x)
- `L` — large sprite (2x)
- `XL` — boss sprite (2.5x, visually distinct)

#### Scenario: XL complexity change
- **WHEN** a change has `complexity: "XL"`
- **THEN** it MUST render as a larger, visually distinct "boss" sprite

### Requirement: Progress Indicators on Running Changes
Running changes in the atmosphere zone SHALL display:
- A progress bar (estimated from token usage vs budget or elapsed time)
- Current token rate (tokens/second)
- Change name label

#### Scenario: Running change with token data
- **WHEN** a change is running and has `input_tokens` and `output_tokens` values
- **THEN** the sprite MUST show a progress bar and token rate below it

### Requirement: Ralph Character
A character named "Ralph" SHALL appear at the bottom of the screen representing the AI agent system. Ralph's appearance MUST reflect current activity:

| State | Appearance |
|-------|-----------|
| No changes running | Sleeping (closed eyes, "zzz") |
| 1-2 changes running | Working (alert eyes, single lightning) |
| 3+ changes running | Multithreading (wide eyes, multiple arms, triple lightning) |
| Change just completed | Celebrating (happy face, raised arms) |
| Change just failed | Sweating (X eyes, sweat drops) |
| All changes done | Victory pose (star eyes, trophy) |

#### Scenario: Parallel execution starts
- **WHEN** 3 or more changes are in `running` status simultaneously
- **THEN** Ralph MUST switch to the "multithreading" appearance

#### Scenario: Change failure occurs
- **WHEN** a change transitions to `failed` status
- **THEN** Ralph MUST briefly show the "sweating" appearance for at least 2 seconds

### Requirement: Live Event Feed
The battle view SHALL include a scrolling event feed showing orchestration events with colorful narration:
- State transitions (dispatched, running, failed, done, merged)
- Score changes
- Achievement unlocks

The feed MUST show the most recent 20 events with timestamps.

#### Scenario: Change dispatched
- **WHEN** a change is dispatched
- **THEN** the feed MUST show an entry like "🛸 {name} DISPATCHED" with timestamp

#### Scenario: Change failed
- **WHEN** a change fails
- **THEN** the feed MUST show an entry like "💥 {name} EXPLODED — {reason}" with timestamp

### Requirement: Tab Integration
The battle view MUST be accessible as a tab labeled "Battle" in the dashboard tab bar, alongside existing tabs (Changes, Phases, Log, etc.).

#### Scenario: Tab appears during active orchestration
- **WHEN** a project has any orchestration state (idle or active)
- **THEN** the "Battle" tab MUST be visible in the tab bar

### Requirement: Responsive Layout
The battle view MUST work on both desktop and mobile viewports.
- Desktop: full layout with all zones, Ralph, feed, and score
- Mobile: compact vertical layout with smaller sprites and collapsed feed

#### Scenario: Mobile viewport
- **WHEN** the viewport width is less than 768px
- **THEN** the layout MUST switch to a compact vertical arrangement with smaller sprites

### Requirement: Data Source
The battle view SHALL use the same data sources as the existing Dashboard:
- REST polling via `/api/{project}/state` for periodic updates
- WebSocket events for real-time state transitions
- No new API endpoints required

#### Scenario: WebSocket event received
- **WHEN** a `state_update` WebSocket event is received
- **THEN** the battle view MUST update sprite positions and trigger animations within 200ms
