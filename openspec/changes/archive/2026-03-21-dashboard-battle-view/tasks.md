# Dashboard Battle View — Tasks

## 1. Core Infrastructure

- [x] 1.1 Create BattleView page component — Create `web/src/pages/BattleView.tsx` with the basic layout structure: BattleHeader, BattleCanvas, EventFeed, and AchievementBar areas. Wire up state polling (same pattern as Dashboard — `useWebSocket` + REST fallback). Accept `project` prop.

- [x] 1.2 Add Battle tab to Dashboard — In `web/src/pages/Dashboard.tsx`, add "Battle" to the `PanelTab` type and tab bar. In `web/src/App.tsx`, no route change needed — Battle is a tab within the Dashboard, not a separate route.

- [x] 1.3 Create state transition detection — Create `web/src/lib/battleTransitions.ts`. Implement `detectTransitions(prev, next)` that compares two `ChangeInfo[]` arrays and returns a list of `ChangeTransition` objects (name, from-status, to-status, change data). This drives all animations, scoring, and event feed.

## 2. Canvas Rendering

- [x] 2.1 Create BattleCanvas component — Create `web/src/components/battle/BattleCanvas.tsx`. Set up a `<canvas>` element with `requestAnimationFrame` loop. Handle resize (fill parent container). Define the three zones (orbit, atmosphere, ground) as Y-coordinate ranges. Render zone separator lines with labels.

- [x] 2.2 Implement sprite system — Create `web/src/lib/battleSprites.ts`. Define `Sprite` interface and `SpriteManager` class that creates/removes sprites based on change list, assigns X positions (spread evenly, avoid overlap), sets Y position based on zone (orbit=top, atmosphere=middle, ground=bottom), and updates sprite size based on `complexity` field (S=1x, M=1.5x, L=2x, XL=2.5x).

- [x] 2.3 Draw sprites on canvas — In BattleCanvas, render each sprite per frame: Orbit: emoji 👾 with gentle sine-wave float animation. Atmosphere: emoji 🛸 with progress bar below, token rate text, change name. Ground: emoji ✅ with change name. Failed: emoji 💥 with particle scatter. Stalled: emoji ⚠️ with blink.

- [x] 2.4 Animate state transitions — When `detectTransitions` fires: `pending → running`: sprite animates from orbit Y to atmosphere Y (smooth lerp over 1s). `running → failed`: explosion particle effect (0.5s), then rebuild animation (🔧 spinning, 1s). `running → done/merged`: landing animation to ground Y (0.5s), brief confetti particles. `failed → running` (retry): rebuild → re-enter atmosphere.

- [x] 2.5 Implement Ralph character — Draw Ralph at bottom-center of canvas using canvas text/shapes. Body: simple geometric shapes (rectangle body, circle head). Face: emoji-style eyes and mouth drawn with canvas arcs. State-dependent appearance (sleeping/working/multithreading/celebrating/sweating/victory). Mood derived from running change count + recent transitions (2s override for celebrating/sweating).

## 3. Scoring System

- [x] 3.1 Create score engine — Create `web/src/lib/battleScoring.ts`. Implement `ScoreEngine` class with `processTransition(transition, allChanges)` returning point delta and reason. Point values per the scoring spec (1000 first-try, 500 retry, etc.). Token efficiency bonus, duration bonus, and penalty calculation.

- [x] 3.2 Implement multiplier system — In ScoreEngine, track and apply multipliers: count running changes → 2x for 2 parallel, 3x for 3+. Track phase failures → 1.5x phase streak if current phase has 0 failures. Multipliers apply to gains only, not penalties. Stack multiplicatively.

- [x] 3.3 Implement lives system — In ScoreEngine, track cumulative failure count. Lose 1 life per 3 failures (start with 3 lives). When lives hit 0, emit a "game over" event. "Continue?" resets lives but keeps score.

- [x] 3.4 Create BattleHeader component — Create `web/src/components/battle/BattleHeader.tsx`. Display: current score (animated counter), high score, current multiplier (e.g., "x2"), lives (hearts), "NEW HIGH SCORE!" flash when exceeded.

- [x] 3.5 Implement score persistence — Save/load score state to localStorage with key `set-battle-score-{projectName}`. Save on every score change. Load on component mount. Track high score separately.

## 4. Achievements

- [x] 4.1 Create achievement definitions — In `battleScoring.ts`, define all 15 achievements with ID, name, description, rarity (common/uncommon/rare/epic/legendary), bonus points on unlock, and check function.

- [x] 4.2 Create AchievementBar component — Create `web/src/components/battle/AchievementBar.tsx`. Render a horizontal row of achievement icons. Unlocked: colored with emoji and name tooltip. Locked: gray lock with "???" tooltip. Click to see description.

- [x] 4.3 Create AchievementPopup component — Create `web/src/components/battle/AchievementPopup.tsx`. When an achievement unlocks: slide in from top, centered. Show name, description, bonus points, rarity badge. Auto-dismiss after 3 seconds. Queue multiple unlocks.

- [x] 4.4 Persist achievements — Save unlocked achievements to localStorage alongside score. Key: `set-battle-achievements-{projectName}`.

## 5. Event Feed

- [x] 5.1 Create EventFeed component — Create `web/src/components/battle/EventFeed.tsx`. Scrollable list of max 20 events with timestamp, emoji icon based on event type, colorful narrated description, score change indicator (+1000, -200, etc.).

- [x] 5.2 Generate narrated events — On each transition, generate a narrated event string. Dispatched: "🛸 {name} DISPATCHED". Running: "🚀 {name} entering atmosphere". Failed: "💥 {name} EXPLODED". Done: "✅ {name} LANDED (+{points})". Achievement: "🏆 ACHIEVEMENT: {name}". Retry: "🔧 {name} REBUILDING (attempt {n})".

## 6. Responsive & Polish

- [x] 6.1 Mobile layout — Add responsive breakpoints to BattleView. Desktop (>=768px): full layout with side-by-side achievement bar and event feed. Mobile (<768px): stacked vertical layout, smaller canvas, collapsed feed (tap to expand).

- [x] 6.2 Game Over overlay — When lives reach 0, render a semi-transparent overlay on the canvas. "GAME OVER" text, final score, "Continue?" button (resets lives, keeps score), achievement summary.

- [x] 6.3 Idle/empty state — When no orchestration is active: Ralph sleeping animation, "Waiting for orchestration..." text, show high score and past achievements.
