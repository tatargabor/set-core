import type { ChangeInfo } from './api'

export type SpriteZone = 'orbit' | 'atmosphere' | 'ground'
export type SpriteAnimation = 'idle' | 'descending' | 'exploding' | 'rebuilding' | 'landing' | 'celebrating'

export interface Sprite {
  id: string
  x: number
  y: number
  targetY: number
  zone: SpriteZone
  status: string
  size: number
  progress: number
  tokensPerSec: number
  animation: SpriteAnimation
  animFrame: number
  animStart: number
  name: string
  // Movement
  vx: number
  vy: number
  movePattern: 'linear' | 'sine' | 'zigzag' | 'erratic'
  moveSpeed: number
  movePhase: number
  // Combat
  hp: number
  maxHp: number
  hitCount: number
  invulnFrames: number
  // Ghost state: killed by player, stays as ghost until respawn
  ghost: boolean
  ghostSince: number  // timestamp when became ghost (0 = not ghost)
}

/** Mini sprites that spawn when a main sprite is killed */
export interface Minion {
  id: string
  parentName: string
  x: number
  y: number
  vx: number
  vy: number
  size: number
  spawnTime: number
  ttl: number  // time to live in ms
  hp: number
}

const ZONE_PENDING = ['pending']
const ZONE_DONE = ['done', 'merged', 'completed', 'skip_merged', 'skipped']

function statusToZone(status: string): SpriteZone {
  if (ZONE_PENDING.includes(status)) return 'orbit'
  if (ZONE_DONE.includes(status)) return 'ground'
  return 'atmosphere'
}

function complexityToSize(complexity?: string): number {
  switch (complexity) {
    case 'S': return 1
    case 'M': return 1.5
    case 'L': return 2
    case 'XL': return 2.5
    default: return 1.5
  }
}

function complexityToHp(complexity?: string): number {
  switch (complexity) {
    case 'S': return 1
    case 'M': return 1
    case 'L': return 2
    case 'XL': return 3
    default: return 1
  }
}

export function getZoneY(zone: SpriteZone, canvasHeight: number): { min: number; max: number } {
  const h = canvasHeight
  switch (zone) {
    case 'orbit': return { min: h * 0.05, max: h * 0.25 }
    case 'atmosphere': return { min: h * 0.30, max: h * 0.65 }
    case 'ground': return { min: h * 0.75, max: h * 0.85 }
  }
}

export class SpriteManager {
  sprites: Map<string, Sprite> = new Map()
  minions: Minion[] = []
  private minionIdCounter = 0

  update(changes: ChangeInfo[], canvasWidth: number, canvasHeight: number, now: number) {
    const currentIds = new Set(changes.map(c => c.name))

    for (const id of this.sprites.keys()) {
      if (!currentIds.has(id)) this.sprites.delete(id)
    }

    const byZone: Record<SpriteZone, ChangeInfo[]> = { orbit: [], atmosphere: [], ground: [] }
    for (const c of changes) {
      byZone[statusToZone(c.status)].push(c)
    }

    for (const c of changes) {
      const zone = statusToZone(c.status)
      const zoneY = getZoneY(zone, canvasHeight)
      const zoneChanges = byZone[zone]
      const idx = zoneChanges.indexOf(c)
      const count = zoneChanges.length
      const spacing = canvasWidth / (count + 1)
      const targetX = spacing * (idx + 1)
      const targetY = zoneY.min + (zoneY.max - zoneY.min) * (idx % 3) / 3

      const existing = this.sprites.get(c.name)
      if (existing) {
        const oldZone = existing.zone
        const oldStatus = existing.status
        existing.status = c.status
        existing.zone = zone
        existing.targetY = targetY
        existing.progress = estimateProgress(c)
        existing.tokensPerSec = estimateTokPerSec(c)
        existing.size = complexityToSize(c.complexity)

        // Status changed in orchestration → un-ghost (respawn)
        if (oldStatus !== c.status) {
          existing.ghost = false
          existing.ghostSince = 0
          existing.hp = existing.maxHp
          existing.hitCount = 0
          existing.movePattern = 'linear'
          existing.moveSpeed = 1
        }

        // Ghost respawn after ~15 seconds
        if (existing.ghost && existing.ghostSince > 0 && now - existing.ghostSince > 15000) {
          existing.ghost = false
          existing.ghostSince = 0
          existing.hp = existing.maxHp
          existing.hitCount = 0
          existing.movePattern = 'linear'
          existing.moveSpeed = 1 + Math.random() * 0.5
          existing.vx = (Math.random() - 0.5) * 3
        }

        if (oldZone !== zone) {
          if (zone === 'ground') {
            existing.animation = 'landing'
            existing.animStart = now
            existing.ghost = false  // landed = real
          } else if (zone === 'atmosphere' && oldZone === 'orbit') {
            existing.animation = 'descending'
            existing.animStart = now
          }
        }

        if (c.status === 'failed' || c.status === 'verify-failed') {
          if (existing.animation !== 'exploding' && existing.animation !== 'rebuilding') {
            existing.animation = 'exploding'
            existing.animStart = now
          }
        }

        if (existing.invulnFrames > 0) existing.invulnFrames--

        // Smooth X for non-ghost
        if (!existing.ghost) {
          existing.x += (targetX - existing.x) * 0.05
        }
      } else {
        const maxHp = complexityToHp(c.complexity)
        this.sprites.set(c.name, {
          id: c.name,
          name: c.name,
          x: targetX,
          y: targetY,
          targetY,
          zone,
          status: c.status,
          size: complexityToSize(c.complexity),
          progress: estimateProgress(c),
          tokensPerSec: estimateTokPerSec(c),
          animation: 'idle',
          animFrame: 0,
          animStart: now,
          vx: (Math.random() - 0.5) * 2,
          vy: 0,
          movePattern: 'linear',
          moveSpeed: 1,
          movePhase: Math.random() * Math.PI * 2,
          hp: maxHp,
          maxHp,
          hitCount: 0,
          invulnFrames: 0,
          ghost: false,
          ghostSince: 0,
        })
      }
    }

    // --- Animate sprites ---
    for (const s of this.sprites.values()) {
      s.animFrame++
      const t = now / 1000

      if (s.zone === 'ground') {
        s.y += (s.targetY - s.y) * 0.08
        s.x += (getZoneX(s, canvasWidth, changes) - s.x) * 0.05
        continue
      }

      // Ghost sprites drift slowly, don't do combat movement
      if (s.ghost) {
        s.y += (s.targetY - s.y) * 0.02
        continue
      }

      const speed = s.moveSpeed * (1 + s.hitCount * 0.4)

      if (s.zone === 'orbit') {
        switch (s.movePattern) {
          case 'linear':
            s.x += s.vx * speed
            if (s.x < 30 || s.x > canvasWidth - 30) s.vx *= -1
            break
          case 'sine':
            s.x += s.vx * speed
            s.y = s.targetY + Math.sin(t * 2 + s.movePhase) * 15
            if (s.x < 30 || s.x > canvasWidth - 30) s.vx *= -1
            break
          case 'zigzag':
            s.x += s.vx * speed * 1.5
            if (s.x < 30 || s.x > canvasWidth - 30) s.vx *= -1
            s.y = s.targetY + Math.sin(t * 4 + s.movePhase) * 20
            break
          case 'erratic':
            s.x += s.vx * speed * 2
            if (Math.random() < 0.02) s.vx *= -1
            if (s.x < 30 || s.x > canvasWidth - 30) s.vx *= -1
            s.y = s.targetY + Math.sin(t * 3 + s.movePhase) * 25 + Math.cos(t * 7) * 10
            break
        }
      } else if (s.zone === 'atmosphere') {
        switch (s.movePattern) {
          case 'linear':
            s.x += s.vx * speed * 0.8
            if (s.x < 30 || s.x > canvasWidth - 30) s.vx *= -1
            break
          case 'sine':
            s.x += Math.sin(t * 1.5 + s.movePhase) * speed * 2
            break
          case 'zigzag':
            s.x += s.vx * speed * 1.2
            if (s.x < 40 || s.x > canvasWidth - 40) s.vx *= -1
            s.y += Math.sin(t * 3) * 0.5
            break
          case 'erratic':
            s.x += s.vx * speed * 1.8
            s.y += Math.sin(t * 5 + s.movePhase) * 1.5
            if (Math.random() < 0.03) s.vx *= -1
            if (s.x < 30 || s.x > canvasWidth - 30) s.vx *= -1
            break
        }
        s.y += (s.targetY - s.y) * 0.02
      }
    }

    // --- Update minions ---
    for (let i = this.minions.length - 1; i >= 0; i--) {
      const m = this.minions[i]
      m.x += m.vx
      m.y += m.vy

      // Bounce off walls
      if (m.x < 20 || m.x > canvasWidth - 20) m.vx *= -1

      // Slow down approach to ralph zone
      if (m.y > canvasHeight * 0.85) m.vy *= 0.95

      // TTL check
      if (now - m.spawnTime > m.ttl) {
        this.minions.splice(i, 1)
      }
    }
  }

  /** Hit a main sprite. Returns points and spawns minions if destroyed. */
  hitSprite(id: string, _canvasHeight: number): { points: number; destroyed: boolean } {
    const s = this.sprites.get(id)
    if (!s || s.zone === 'ground' || s.ghost || s.invulnFrames > 0) return { points: 0, destroyed: false }

    s.hp--
    s.hitCount++
    s.invulnFrames = 15

    const pointsPerHit = s.zone === 'orbit' ? 200 : 500

    if (s.hp <= 0) {
      // KILLED → become ghost + spawn minions
      s.ghost = true
      s.ghostSince = performance.now()

      const adjustedCount = Math.max(1, Math.round(s.size))
      for (let i = 0; i < adjustedCount; i++) {
        this.minions.push({
          id: `minion-${this.minionIdCounter++}`,
          parentName: s.name,
          x: s.x + (Math.random() - 0.5) * 40,
          y: s.y + 20,
          vx: (Math.random() - 0.5) * 3,
          vy: 1 + Math.random() * 2, // move down toward Ralph
          size: 0.5 + Math.random() * 0.3,
          spawnTime: performance.now(),
          ttl: 4000 + Math.random() * 3000, // 4-7 seconds
          hp: 1,
        })
      }

      return { points: pointsPerHit * 2, destroyed: true }
    }

    // Bounce away on hit
    s.vx = (Math.random() - 0.5) * 4

    return { points: pointsPerHit, destroyed: false }
  }

  /** Hit a minion. Returns points. */
  hitMinion(idx: number): number {
    if (idx < 0 || idx >= this.minions.length) return 0
    this.minions.splice(idx, 1)
    return 150
  }
}

function getZoneX(s: Sprite, canvasWidth: number, changes: ChangeInfo[]): number {
  const zoneChanges = changes.filter(c => statusToZone(c.status) === s.zone)
  const idx = zoneChanges.findIndex(c => c.name === s.name)
  if (idx < 0) return s.x
  const spacing = canvasWidth / (zoneChanges.length + 1)
  return spacing * (idx + 1)
}

function estimateProgress(c: ChangeInfo): number {
  if (!c.started_at) return 0
  const elapsed = (Date.now() - new Date(c.started_at).getTime()) / 1000
  return Math.min(0.95, elapsed / 600)
}

function estimateTokPerSec(c: ChangeInfo): number {
  if (!c.started_at || !c.output_tokens) return 0
  const elapsed = (Date.now() - new Date(c.started_at).getTime()) / 1000
  if (elapsed < 1) return 0
  return Math.round(c.output_tokens / elapsed)
}
