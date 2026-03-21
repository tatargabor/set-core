# Dashboard Battle View — Design

## Architecture

### Component Tree

```
Dashboard (existing)
  └── tab: "battle"
      └── BattleView (new page-level component)
          ├── BattleHeader        — score, lives, multiplier, high score
          ├── BattleCanvas        — main game area (Canvas 2D)
          │   ├── OrbitZone       — pending sprites (top)
          │   ├── AtmosphereZone  — running sprites (middle)
          │   ├── GroundZone      — completed sprites (bottom)
          │   ├── Ralph           — character at bottom
          │   └── Explosions      — particle effects
          ├── EventFeed           — scrolling narrated event log
          ├── AchievementBar      — unlocked/locked achievements
          └── AchievementPopup    — temporary unlock notification
```

### Rendering Approach: Canvas 2D

Use HTML5 Canvas for the main game area. Reasons:
- Smooth 60fps animations (sprite movement, explosions, particles)
- Efficient for many moving objects
- No DOM node overhead for sprites
- Easy sprite drawing with emoji or simple geometric shapes

The header, event feed, and achievement bar use normal React DOM (they don't need animation performance).

### Layout

```
┌─────────────────────────────────────────────┐
│ BattleHeader (React DOM)                    │
│ Score: 4200  Hi: 8400  x2  ♥♥♥             │
├─────────────────────────────────────────────┤
│                                             │
│ BattleCanvas (Canvas 2D)                    │
│                                             │
│  ══ ORBIT ══════════════════════════════    │
│  sprites float left-right                   │
│                                             │
│  ══ ATMOSPHERE ════════════════════════     │
│  sprites descend with progress bars         │
│                                             │
│  ══ GROUND ════════════════════════════     │
│  landed sprites with checkmarks             │
│            ▲ RALPH ▲                        │
├──────────────────────┬──────────────────────┤
│ AchievementBar       │ EventFeed            │
│ 🏆🏆🔒🔒🔒            │ 19:42 db LANDED      │
│                      │ 19:41 auth EXPLODED  │
└──────────────────────┴──────────────────────┘
```

Mobile layout stacks everything vertically with a smaller canvas.

### Data Flow

```
 Existing API (no changes)
 ┌────────────────────┐
 │ /api/{proj}/state   │──── REST poll (5s) ────┐
 │ WebSocket events    │──── real-time ──────────┤
 └────────────────────┘                         │
                                                 ▼
                                          ┌─────────────┐
                                          │ BattleView   │
                                          │              │
                                          │ state diff → │
                                          │ detect       │
                                          │ transitions  │
                                          └──────┬──────┘
                                                 │
                              ┌──────────────────┼──────────────────┐
                              ▼                  ▼                  ▼
                        ┌──────────┐     ┌──────────────┐   ┌──────────┐
                        │ Sprites  │     │ ScoreEngine  │   │ EventFeed│
                        │ position │     │ calculate    │   │ append   │
                        │ animate  │     │ achievements │   │ narrate  │
                        └──────────┘     └──────────────┘   └──────────┘
```

### State Transition Detection

BattleView compares previous state with new state on each update:

```typescript
interface ChangeTransition {
  name: string
  from: string   // previous status
  to: string     // new status
  change: ChangeInfo
}

function detectTransitions(prev: ChangeInfo[], next: ChangeInfo[]): ChangeTransition[]
```

Each transition triggers:
1. Sprite animation (move/explode/land)
2. Score update
3. Event feed entry
4. Achievement check

### Sprite System

Sprites are simple objects rendered on canvas each frame:

```typescript
interface Sprite {
  id: string           // change name
  x: number            // canvas x position
  y: number            // canvas y position
  targetY: number      // where it's moving to
  zone: 'orbit' | 'atmosphere' | 'ground'
  status: string       // change status
  size: number         // based on complexity
  progress?: number    // 0-1 for running changes
  tokensPerSec?: number
  animation?: 'idle' | 'descending' | 'exploding' | 'rebuilding' | 'landing' | 'celebrating'
  animFrame: number    // current animation frame
}
```

Orbit sprites float with a gentle sine wave motion.
Atmosphere sprites descend at a rate proportional to their progress.
Ground sprites are static with a brief landing animation.

### Score Engine

```typescript
interface ScoreState {
  score: number
  highScore: number
  lives: number
  multiplier: number
  achievements: Set<string>
  failureCount: number
  consecutiveFirstTry: number
  phaseFailures: Map<number, number>
}
```

Score state lives in React state and is saved to localStorage on every change. Key format: `set-battle-score-{projectName}`.

### Ralph Character

Ralph is rendered on the canvas as a simple ASCII-art-inspired character using canvas text drawing. His state is derived from:

```typescript
type RalphMood = 'sleeping' | 'working' | 'multithreading' | 'celebrating' | 'sweating' | 'victory'

function getRalphMood(changes: ChangeInfo[], recentTransitions: ChangeTransition[]): RalphMood
```

Ralph's mood is derived from:
- Count of running changes (sleeping/working/multithreading)
- Recent transitions override (celebrating/sweating) for 2 seconds
- All done = victory

### File Structure

```
web/src/
  pages/
    BattleView.tsx          — main component, state management
  components/battle/
    BattleHeader.tsx         — score, lives, multiplier display
    BattleCanvas.tsx         — canvas rendering, animation loop
    EventFeed.tsx            — scrolling event log
    AchievementBar.tsx       — achievement display
    AchievementPopup.tsx     — unlock notification
  lib/
    battleScoring.ts         — score calculation, achievement checks
    battleSprites.ts         — sprite management, position calculations
    battleTransitions.ts     — state diff, transition detection
```

## Key Decisions

1. **Canvas 2D over CSS animations** — better performance for many moving objects, simpler particle effects
2. **No new API endpoints** — reuses existing state polling and WebSocket, zero backend work
3. **Emoji sprites over image assets** — no asset loading, works everywhere, fits the playful tone
4. **localStorage for persistence** — simple, no backend storage needed, per-project isolation
5. **Spectator mode only** — Ralph acts autonomously, no user input needed (reduces complexity, matches the "watching orchestration" use case)
6. **requestAnimationFrame loop** — smooth 60fps canvas updates, pauses when tab is hidden
