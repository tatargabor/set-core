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

  update(changes: ChangeInfo[], canvasWidth: number, canvasHeight: number, now: number) {
    const currentIds = new Set(changes.map(c => c.name))

    // Remove sprites for changes that no longer exist
    for (const id of this.sprites.keys()) {
      if (!currentIds.has(id)) this.sprites.delete(id)
    }

    // Group by zone for X positioning
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
        // Update existing sprite
        const oldZone = existing.zone
        existing.status = c.status
        existing.zone = zone
        existing.targetY = targetY
        existing.progress = estimateProgress(c)
        existing.tokensPerSec = estimateTokPerSec(c)
        existing.size = complexityToSize(c.complexity)

        // Trigger animation on zone change
        if (oldZone !== zone) {
          if (zone === 'ground') {
            existing.animation = 'landing'
            existing.animStart = now
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

        // Smooth X movement
        existing.x += (targetX - existing.x) * 0.05
      } else {
        // Create new sprite
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
        })
      }
    }

    // Animate Y positions
    for (const s of this.sprites.values()) {
      s.y += (s.targetY - s.y) * 0.08
      s.animFrame++
    }
  }
}

function estimateProgress(c: ChangeInfo): number {
  if (!c.started_at) return 0
  const elapsed = (Date.now() - new Date(c.started_at).getTime()) / 1000
  // Rough estimate: most changes take 5-15 min
  return Math.min(0.95, elapsed / 600)
}

function estimateTokPerSec(c: ChangeInfo): number {
  if (!c.started_at || !c.output_tokens) return 0
  const elapsed = (Date.now() - new Date(c.started_at).getTime()) / 1000
  if (elapsed < 1) return 0
  return Math.round(c.output_tokens / elapsed)
}
