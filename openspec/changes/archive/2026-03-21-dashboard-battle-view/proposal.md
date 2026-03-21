# Dashboard Battle View

## Why
During orchestration runs, users watch the dashboard passively — refreshing, waiting, checking progress. The existing table view is functional but uninspiring. A gamified "Space Invaders" visualization of the orchestration pipeline would make monitoring engaging, provide at-a-glance status through spatial positioning, and add personality to the tool.

## What Changes
- Add a new "Battle" tab to the web dashboard's project view
- Render orchestration changes as space invaders descending through pipeline stages (orbit → atmosphere → ground)
- Animate transitions between states (dispatch, running, failed, verified, merged)
- Show a "Ralph" character as the AI agent defender at the bottom
- Implement a scoring system derived from real orchestration metrics (tokens, duration, retries)
- Add an achievement system that unlocks based on orchestration events
- Include a live event feed with colorful narration

## Capabilities

### New Capabilities
- `battle-view` — Space Invaders style visualization of orchestration state
- `battle-scoring` — Score and achievement system based on orchestration metrics

### Modified Capabilities
_(none — this is a purely additive UI feature)_

## Impact
- **New files**: React components under `web/src/components/battle/` and a new page `web/src/pages/BattleView.tsx`
- **Modified**: `web/src/App.tsx` (add Battle tab route), `web/src/pages/Dashboard.tsx` (add tab)
- **Dependencies**: No new npm packages — uses Canvas 2D API or CSS animations
- **Backend**: No changes — uses existing `/api/{project}/state` and WebSocket events
- **Risk**: Low — purely additive frontend feature, no backend changes
