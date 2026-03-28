import { useRef, useEffect, useCallback } from 'react'
import type { ChangeInfo } from '../../lib/api'
import { SpriteManager, getZoneY } from '../../lib/battleSprites'

interface Bullet {
  x: number
  y: number
  speed: number
}

interface HitEffect {
  x: number
  y: number
  frame: number
  name: string
  points: number
  destroyed: boolean
}

interface EnemyBullet {
  x: number
  y: number
  speed: number
  char: string
}

export interface Announcement {
  text: string
  sub: string
  color: string
  time: number  // performance.now() when created
}

/** News ships that fly across the screen carrying event text */
export interface NewsShip {
  id: number
  text: string
  color: string
  y: number       // vertical position
  speed: number   // pixels per frame (positive = right, negative = left)
  x: number       // current X
  time: number    // spawn time
  icon: string    // ASCII art prefix
}

interface Props {
  changes: ChangeInfo[]
  gameOver: boolean
  announcements: Announcement[]
  newsShips: NewsShip[]
  isVisible: boolean
  onContinue: () => void
  onHit: (changeName: string, points: number, combo: number) => void
  onRalphHit: () => void
}

type RalphMood = 'sleeping' | 'working' | 'multithreading' | 'celebrating' | 'sweating' | 'victory'

function getRalphMood(changes: ChangeInfo[]): RalphMood {
  const running = changes.filter(c => ['running', 'implementing', 'verifying', 'dispatched'].includes(c.status)).length
  const allDone = changes.length > 0 && changes.every(c => ['done', 'merged', 'completed', 'skip_merged', 'skipped'].includes(c.status))
  if (allDone) return 'victory'
  if (running >= 3) return 'multithreading'
  if (running >= 1) return 'working'
  return 'sleeping'
}

// ASCII invader frames (2-frame animation)
const INVADER_A = [
  '  /\\__/\\  ',
  ' |  ><  | ',
  '  \\    /  ',
  '  /|  |\\  ',
]
const INVADER_B = [
  '  /\\__/\\  ',
  ' |  <>  | ',
  '  \\    /  ',
  '  \\|  |/  ',
]
const SHIP_A = [
  ' _{==}_ ',
  '|      |',
  ' \\    / ',
  '  \\][/  ',
]
const SHIP_B = [
  ' _{==}_ ',
  '|  ..  |',
  ' \\    / ',
  '  \\)(/  ',
]
const BOSS = [
  ' __/====\\__ ',
  '|  [><><]  |',
  '|__/    \\__|',
  '  /| !! |\\  ',
  '  \\|    |/  ',
]
const EXPLODE_1 = [
  '  \\ | /  ',
  ' --   -- ',
  '  / | \\  ',
]
const EXPLODE_2 = [
  '  * . *  ',
  ' . \' * . ',
  '  * . *  ',
]
const EXPLODE_3 = [
  '  .   .  ',
  '    .    ',
  '  .   .  ',
]
const LANDED = [
  '  [OK]  ',
]
const REBUILD = [
  ' {....} ',
  '  \\../  ',
]
const STALLED = [
  '  /??\\  ',
  ' | ?? | ',
  '  \\??/  ',
]

const RALPH_SHIP = [
  '    /\\    ',
  '   /  \\   ',
  '  / () \\  ',
  ' /______\\ ',
  '  ||  ||  ',
]

export default function BattleCanvas({ changes, gameOver, announcements, newsShips, isVisible, onContinue, onHit, onRalphHit }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const spriteManagerRef = useRef(new SpriteManager())
  const rafRef = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const ralphXRef = useRef(0)
  const bulletsRef = useRef<Bullet[]>([])
  const hitsRef = useRef<HitEffect[]>([])
  const keysRef = useRef<Set<string>>(new Set())
  const lastShotRef = useRef(0)
  const comboRef = useRef(0)
  const lastHitTimeRef = useRef(0)
  const enemyBulletsRef = useRef<EnemyBullet[]>([])
  const ralphInvulnRef = useRef(0)
  const ralphHitFlashRef = useRef(0)
  const lastEnemyShotRef = useRef(0)
  const pausedRef = useRef(false)
  const countdownRef = useRef(0) // 3, 2, 1, 0
  const countdownStartRef = useRef(0)

  // Pause on browser tab switch
  useEffect(() => {
    const onVisChange = () => {
      if (document.hidden) {
        pausedRef.current = true
      } else if (isVisible) {
        countdownRef.current = 3
        countdownStartRef.current = performance.now()
      }
    }
    document.addEventListener('visibilitychange', onVisChange)
    return () => document.removeEventListener('visibilitychange', onVisChange)
  }, [isVisible])

  // Pause on dashboard tab switch (isVisible prop)
  const wasVisibleRef = useRef(isVisible)
  useEffect(() => {
    if (!isVisible && wasVisibleRef.current) {
      // Left battle tab → pause
      pausedRef.current = true
    } else if (isVisible && !wasVisibleRef.current) {
      // Returned to battle tab → countdown
      countdownRef.current = 3
      countdownStartRef.current = performance.now()
    }
    wasVisibleRef.current = isVisible
  }, [isVisible])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', ' ', 'Space'].includes(e.key)) {
        e.preventDefault()
        e.stopPropagation()
        keysRef.current.add(e.key)
      }
    }
    const onKeyUp = (e: KeyboardEvent) => {
      keysRef.current.delete(e.key)
    }
    // Use capture phase to intercept before any other handler
    window.addEventListener('keydown', onKeyDown, { capture: true })
    window.addEventListener('keyup', onKeyUp, { capture: true })
    return () => {
      window.removeEventListener('keydown', onKeyDown, { capture: true })
      window.removeEventListener('keyup', onKeyUp, { capture: true })
    }
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    let touchStartX = 0
    const onTouchStart = (e: TouchEvent) => {
      e.preventDefault()
      touchStartX = e.touches[0].clientX
      const now = performance.now()
      if (now - lastShotRef.current > 200) {
        lastShotRef.current = now
        bulletsRef.current.push({ x: ralphXRef.current, y: canvas.height * 0.86, speed: 7 })
      }
    }
    const onTouchMove = (e: TouchEvent) => {
      e.preventDefault()
      const dx = e.touches[0].clientX - touchStartX
      touchStartX = e.touches[0].clientX
      ralphXRef.current += dx
    }
    canvas.addEventListener('touchstart', onTouchStart, { passive: false })
    canvas.addEventListener('touchmove', onTouchMove, { passive: false })
    return () => { canvas.removeEventListener('touchstart', onTouchStart); canvas.removeEventListener('touchmove', onTouchMove) }
  }, [])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const w = canvas.width
    const h = canvas.height
    const now = performance.now()

    // Skip drawing if canvas has no size (hidden)
    if (w === 0 || h === 0) {
      rafRef.current = requestAnimationFrame(draw)
      return
    }

    const sm = spriteManagerRef.current
    const keys = keysRef.current
    const FONT = 'monospace'

    if (ralphXRef.current === 0) ralphXRef.current = w / 2

    // Handle countdown after unpause
    if (countdownRef.current > 0) {
      const elapsed = now - countdownStartRef.current
      const remaining = 3 - Math.floor(elapsed / 1000)
      if (remaining <= 0) {
        countdownRef.current = 0
        pausedRef.current = false
      } else {
        countdownRef.current = remaining
      }
    }

    const isPaused = pausedRef.current || countdownRef.current > 0

    if (now - lastHitTimeRef.current > 2000) comboRef.current = 0

    // Input (disabled when paused)
    if (!gameOver && !isPaused) {
      const speed = 5
      if (keys.has('ArrowLeft')) ralphXRef.current = Math.max(40, ralphXRef.current - speed)
      if (keys.has('ArrowRight')) ralphXRef.current = Math.min(w - 40, ralphXRef.current + speed)
      if (keys.has(' ') || keys.has('Space')) {
        if (now - lastShotRef.current > 200) {
          lastShotRef.current = now
          bulletsRef.current.push({ x: ralphXRef.current, y: h * 0.86, speed: 7 })
        }
      }
    }

    // Update bullets (freeze when paused)
    const bullets = bulletsRef.current
    if (!isPaused) {
      for (let i = bullets.length - 1; i >= 0; i--) {
        bullets[i].y -= bullets[i].speed
        if (bullets[i].y < 0) bullets.splice(i, 1)
      }
    }

    sm.update(changes, w, h, now)

    // Collision: bullets vs main sprites (skip when paused)
    for (let bi = bullets.length - 1; bi >= 0; bi--) {
      const b = bullets[bi]
      let hit = false

      // Check main sprites (skip ghosts and ground)
      for (const s of sm.sprites.values()) {
        if (s.zone === 'ground' || s.ghost || s.invulnFrames > 0) continue
        const hitR = 12 * s.size
        if (Math.abs(b.x - s.x) < hitR && Math.abs(b.y - s.y) < hitR) {
          bullets.splice(bi, 1)
          const result = sm.hitSprite(s.id, h)
          if (result.points > 0) {
            comboRef.current++
            lastHitTimeRef.current = now
            const cm = Math.min(comboRef.current, 5)
            const pts = result.points * cm
            hitsRef.current.push({ x: s.x, y: s.y, frame: 0, name: s.name, points: pts, destroyed: result.destroyed })
            onHit(s.id, pts, comboRef.current)
          }
          hit = true
          break
        }
      }

      // Check minions
      if (!hit && bi < bullets.length) {
        const b2 = bullets[bi]
        for (let mi = sm.minions.length - 1; mi >= 0; mi--) {
          const m = sm.minions[mi]
          if (Math.abs(b2.x - m.x) < 12 && Math.abs(b2.y - m.y) < 12) {
            bullets.splice(bi, 1)
            const pts = sm.hitMinion(mi)
            if (pts > 0) {
              comboRef.current++
              lastHitTimeRef.current = now
              const cm = Math.min(comboRef.current, 5)
              const totalPts = pts * cm
              hitsRef.current.push({ x: m.x, y: m.y, frame: 0, name: 'minion', points: totalPts, destroyed: true })
              onHit('minion', totalPts, comboRef.current)
            }
            break
          }
        }
      }
    }

    // Enemy shooting (paused = no new shots, no collision)
    const enemyBullets = enemyBulletsRef.current
    if (!gameOver && !isPaused && now - lastEnemyShotRef.current > 800) {
      // Pick a random non-ground sprite to shoot
      const shooters = Array.from(sm.sprites.values()).filter(s => s.zone !== 'ground' && !s.ghost && s.invulnFrames === 0)
      if (shooters.length > 0) {
        const shooter = shooters[Math.floor(Math.random() * shooters.length)]
        const chars = ['|', '!', 'v', '*', ':']
        enemyBullets.push({
          x: shooter.x + (Math.random() - 0.5) * 10,
          y: shooter.y + 15,
          speed: 3 + Math.random() * 2,
          char: chars[Math.floor(Math.random() * chars.length)],
        })
        lastEnemyShotRef.current = now
      }
    }

    // Minions also shoot (less frequently, not when paused)
    if (!isPaused && sm.minions.length > 0 && Math.random() < 0.02) {
      const m = sm.minions[Math.floor(Math.random() * sm.minions.length)]
      enemyBullets.push({
        x: m.x, y: m.y + 8, speed: 2.5 + Math.random(),
        char: '.',
      })
    }

    // Update enemy bullets
    for (let i = enemyBullets.length - 1; i >= 0; i--) {
      enemyBullets[i].y += enemyBullets[i].speed
      if (enemyBullets[i].y > h) enemyBullets.splice(i, 1)
    }

    // Enemy bullet vs Ralph collision (skip when paused)
    if (isPaused) {
      // no collision during pause/countdown
    } else if (ralphInvulnRef.current > 0) {
      ralphInvulnRef.current--
    } else {
      const ralphX = ralphXRef.current
      const ralphY = h * 0.91
      for (let i = enemyBullets.length - 1; i >= 0; i--) {
        const eb = enemyBullets[i]
        if (Math.abs(eb.x - ralphX) < 18 && Math.abs(eb.y - ralphY) < 20) {
          enemyBullets.splice(i, 1)
          ralphInvulnRef.current = 90 // ~1.5s at 60fps
          ralphHitFlashRef.current = 20
          comboRef.current = 0 // combo reset on hit
          onRalphHit()
          break
        }
      }
    }
    if (ralphHitFlashRef.current > 0) ralphHitFlashRef.current--

    const hits = hitsRef.current
    for (let i = hits.length - 1; i >= 0; i--) {
      hits[i].frame++
      if (hits[i].frame > 45) hits.splice(i, 1)
    }

    // --- RENDER ---
    ctx.fillStyle = '#050510'
    ctx.fillRect(0, 0, w, h)

    // Warp speed detection: if recent announcement, speed up stars
    const mostRecentAnn = announcements.length > 0
      ? Math.max(...announcements.map(a => a.time))
      : 0
    const mostRecentShip = newsShips.length > 0
      ? Math.max(...newsShips.map(s => s.time))
      : 0
    const lastEventTime = Math.max(mostRecentAnn, mostRecentShip)
    const timeSinceEvent = now - lastEventTime
    // Warp: 0-500ms ramp up, 500-1500ms hold, 1500-2500ms ramp down
    let warpFactor = 1
    if (lastEventTime > 0 && timeSinceEvent < 2500) {
      if (timeSinceEvent < 500) {
        warpFactor = 1 + (timeSinceEvent / 500) * 8 // ramp to 9x
      } else if (timeSinceEvent < 1500) {
        warpFactor = 9 // hold
      } else {
        warpFactor = 9 - ((timeSinceEvent - 1500) / 1000) * 8 // ramp down to 1x
      }
    }

    // Starfield — 3 parallax layers scrolling down
    ctx.textAlign = 'center'
    for (let i = 0; i < 100; i++) {
      const layer = i % 3
      const baseSpeed = [0.01, 0.025, 0.05][layer]
      const speed = baseSpeed * warpFactor
      const fontSize = [8, 10, 12][layer]
      const baseBright = ['#222233', '#334455', '#556677'][layer]
      const chars = ['.', '\u00B7', '*']
      const char = layer === 2 && i % 5 === 0 ? '+' : chars[layer]
      ctx.font = `${fontSize}px ${FONT}`

      const sx = ((i * 137.5 + i * i * 3.7) % w)
      const sy = ((i * 97.3) + now * speed) % h

      if (warpFactor > 2) {
        // Warp streaks: draw lines instead of dots
        const streakLen = Math.min(30, (warpFactor - 1) * 3)
        ctx.strokeStyle = baseBright
        ctx.lineWidth = layer === 2 ? 1.5 : 0.8
        ctx.globalAlpha = Math.min(1, warpFactor / 5)
        ctx.beginPath()
        ctx.moveTo(sx, sy)
        ctx.lineTo(sx, sy - streakLen)
        ctx.stroke()
        ctx.globalAlpha = 1
      } else {
        ctx.fillStyle = baseBright
        ctx.fillText(char, sx, sy)
      }
    }

    // Asteroids — ASCII rocks drifting slowly
    ctx.font = '14px ' + FONT
    for (let i = 0; i < 8; i++) {
      const ax = ((i * 211.7) + now * 0.015 * (i % 2 === 0 ? 1 : -1)) % (w + 80) - 40
      const ay = ((i * 173.3) + now * 0.008) % (h * 0.75) + 10
      const rotation = Math.floor(now / 1500 + i * 0.7) % 4
      ctx.fillStyle = i % 3 === 0 ? '#2a2a35' : '#1e1e28'
      const rocks = ['(@@)', '<##>', '{%%}', '(&&)', '[**]', '|==|', '(::)', '<>>']
      ctx.textAlign = 'center'
      ctx.fillText(rocks[i % rocks.length].slice(0, rotation + 2) + rocks[i % rocks.length].slice(rotation + 2), ax, ay)
    }

    // Scanline effect
    ctx.fillStyle = 'rgba(0, 255, 0, 0.006)'
    for (let sy = 0; sy < h; sy += 3) {
      ctx.fillRect(0, sy, w, 1)
    }

    // Zone dividers (dashed ASCII)
    ctx.font = '10px ' + FONT
    ctx.textAlign = 'left'
    const drawZoneLine = (label: string, yPos: number, color: string) => {
      ctx.fillStyle = color
      const dashes = '\u2500'.repeat(Math.floor(w / 8))
      ctx.fillText(`\u2500\u2500 ${label} ${dashes}`, 4, yPos)
    }

    const orbitZone = getZoneY('orbit', h)
    const atmosZone = getZoneY('atmosphere', h)
    const groundZone = getZoneY('ground', h)

    drawZoneLine('ORBIT', orbitZone.min - 8, '#1a3a1a')
    drawZoneLine('ATMOSPHERE', atmosZone.min - 8, '#1a2a3a')
    drawZoneLine('GROUND', groundZone.min - 8, '#2a2a1a')

    // Helper: draw ASCII art centered at x, y
    const drawAscii = (lines: string[], cx: number, cy: number, color: string, scale: number = 1) => {
      const fontSize = Math.round(11 * scale)
      ctx.font = `${fontSize}px ${FONT}`
      ctx.fillStyle = color
      ctx.textAlign = 'center'
      const lineH = fontSize + 1
      const startY = cy - (lines.length * lineH) / 2
      for (let i = 0; i < lines.length; i++) {
        ctx.fillText(lines[i], cx, startY + i * lineH + lineH)
      }
    }

    // Draw sprites
    const frame = Math.floor(now / 500) % 2
    for (const s of sm.sprites.values()) {
      if (s.invulnFrames > 0 && s.invulnFrames % 4 < 2) continue

      const scale = s.size * 0.8

      // Ghost: translucent + different rendering
      if (s.ghost) {
        ctx.globalAlpha = 0.2 + Math.sin(now / 300) * 0.08
        const ghostArt = [
          '  .----.  ',
          ' : \u00B7  \u00B7 : ',
          ' :  __  : ',
          '  `----\'  ',
        ]
        drawAscii(ghostArt, s.x, s.y, '#445566', scale * 0.7)
        ctx.font = '8px ' + FONT
        ctx.fillStyle = '#334455'
        ctx.textAlign = 'center'
        const short = s.name.length > 16 ? s.name.slice(0, 14) + '..' : s.name
        ctx.fillText(short, s.x, s.y + 22 * scale)
        // Show status under ghost
        ctx.font = '7px ' + FONT
        ctx.fillStyle = '#223344'
        ctx.fillText(`[${s.status}]`, s.x, s.y + 30 * scale)
        ctx.globalAlpha = 1
        continue
      }

      if (s.zone === 'orbit') {
        const art = s.maxHp >= 3
          ? BOSS
          : frame === 0 ? INVADER_A : INVADER_B
        const color = s.maxHp >= 3 ? '#ff6b6b' : s.maxHp >= 2 ? '#ffaa44' : '#44ff88'
        drawAscii(art, s.x, s.y, color, scale)

        ctx.font = '9px ' + FONT
        ctx.fillStyle = '#336633'
        ctx.textAlign = 'center'
        const short = s.name.length > 16 ? s.name.slice(0, 14) + '..' : s.name
        ctx.fillText(short, s.x, s.y + 28 * scale)

      } else if (s.zone === 'atmosphere') {
        if (s.status === 'failed' || s.status === 'verify-failed') {
          const eFrame = Math.floor(now / 300) % 3
          const art = eFrame === 0 ? EXPLODE_1 : eFrame === 1 ? EXPLODE_2 : REBUILD
          drawAscii(art, s.x, s.y, eFrame < 2 ? '#ff4444' : '#ffaa22', scale)
        } else if (s.status === 'stalled') {
          drawAscii(STALLED, s.x, s.y, Math.floor(now / 400) % 2 === 0 ? '#ffaa00' : '#664400', scale)
        } else {
          const art = frame === 0 ? SHIP_A : SHIP_B
          const color = s.status === 'verifying' ? '#44aaff' : '#88ccff'
          drawAscii(art, s.x, s.y, color, scale)
        }

        ctx.font = '9px ' + FONT
        ctx.fillStyle = '#334466'
        ctx.textAlign = 'center'
        const short = s.name.length > 16 ? s.name.slice(0, 14) + '..' : s.name
        ctx.fillText(short, s.x, s.y + 30 * scale)

        if (s.progress > 0 && !['failed', 'verify-failed', 'stalled'].includes(s.status)) {
          const barLen = 12
          const filled = Math.round(s.progress * barLen)
          const bar = '[' + '\u2588'.repeat(filled) + '\u2591'.repeat(barLen - filled) + ']'
          ctx.font = '9px ' + FONT
          ctx.fillStyle = '#336633'
          ctx.fillText(bar, s.x, s.y + 38 * scale)

          if (s.tokensPerSec > 0) {
            ctx.fillStyle = '#223322'
            ctx.fillText(`${s.tokensPerSec}t/s`, s.x, s.y + 48 * scale)
          }
        }

      } else if (s.zone === 'ground') {
        drawAscii(LANDED, s.x, s.y, '#44aa44', scale)
        ctx.font = '9px ' + FONT
        ctx.fillStyle = '#335533'
        ctx.textAlign = 'center'
        const short = s.name.length > 16 ? s.name.slice(0, 14) + '..' : s.name
        ctx.fillText(short, s.x, s.y + 14 * scale)
      }

      // HP bar (ASCII style)
      if (s.maxHp > 1 && s.zone !== 'ground') {
        const hpChars = '\u2665'.repeat(s.hp) + '\u2661'.repeat(s.maxHp - s.hp)
        ctx.font = '9px ' + FONT
        ctx.fillStyle = s.hp > s.maxHp / 2 ? '#44ff44' : s.hp > 1 ? '#ffaa00' : '#ff4444'
        ctx.textAlign = 'center'
        ctx.fillText(hpChars, s.x, s.y - 22 * scale)
      }
    }

    // Draw minions (small fast critters)
    ctx.font = '10px ' + FONT
    ctx.textAlign = 'center'
    for (const m of sm.minions) {
      const age = now - m.spawnTime
      const fadeOut = m.ttl - age < 1000 ? (m.ttl - age) / 1000 : 1
      ctx.globalAlpha = fadeOut * 0.9
      // Animated mini invader
      const mFrame = Math.floor(now / 200) % 2
      ctx.fillStyle = '#ff8844'
      ctx.fillText(mFrame === 0 ? '<\u00B7>' : '>\u00B7<', m.x, m.y)
      ctx.font = '7px ' + FONT
      ctx.fillStyle = '#664422'
      ctx.fillText(m.parentName.slice(0, 6), m.x, m.y + 10)
      ctx.font = '10px ' + FONT
      ctx.globalAlpha = 1
    }

    // Bullets (ASCII style)
    ctx.font = '14px ' + FONT
    ctx.fillStyle = '#ffff44'
    ctx.textAlign = 'center'
    for (const b of bullets) {
      ctx.fillText('|', b.x, b.y)
      ctx.fillStyle = '#aaaa22'
      ctx.fillText(':', b.x, b.y + 10)
      ctx.fillStyle = '#666622'
      ctx.fillText('.', b.x, b.y + 18)
      ctx.fillStyle = '#ffff44'
    }

    // Enemy bullets (ASCII — red, falling down)
    ctx.font = '14px ' + FONT
    ctx.textAlign = 'center'
    for (const eb of enemyBullets) {
      ctx.fillStyle = '#ff4444'
      ctx.fillText(eb.char, eb.x, eb.y)
      ctx.fillStyle = '#aa2222'
      ctx.fillText('.', eb.x, eb.y - 8)
    }

    // Hit effects
    for (const hit of hits) {
      const alpha = 1 - hit.frame / 45
      ctx.globalAlpha = alpha

      if (hit.destroyed) {
        const f = Math.floor(hit.frame / 8)
        const art = f === 0 ? EXPLODE_1 : f === 1 ? EXPLODE_2 : EXPLODE_3
        drawAscii(art, hit.x, hit.y - hit.frame * 0.5, '#ff6644')
      } else {
        ctx.font = '12px ' + FONT
        ctx.fillStyle = '#ffaa44'
        ctx.textAlign = 'center'
        ctx.fillText('*', hit.x, hit.y)
      }

      // Points floating up
      ctx.font = `bold ${hit.destroyed ? 14 : 11}px ${FONT}`
      ctx.fillStyle = '#44ff44'
      ctx.textAlign = 'center'
      ctx.fillText(`+${hit.points}`, hit.x, hit.y - hit.frame * 1.5 - 15)
      ctx.globalAlpha = 1
    }

    // Combo
    const combo = comboRef.current
    if (combo >= 2 && now - lastHitTimeRef.current < 2000) {
      const ca = Math.min(1, 1 - (now - lastHitTimeRef.current) / 2000)
      ctx.globalAlpha = ca
      ctx.font = `bold ${16 + combo * 3}px ${FONT}`
      ctx.fillStyle = combo >= 5 ? '#ff44ff' : combo >= 3 ? '#ffaa44' : '#ffff44'
      ctx.textAlign = 'center'
      ctx.fillText(`=== COMBO x${combo} ===`, w / 2, h * 0.48)
      ctx.globalAlpha = 1
    }

    // Center announcements (orchestration status changes)
    for (const ann of announcements) {
      const age = now - ann.time
      if (age > 6000) continue
      const progress = age / 6000

      // Fade in first 400ms, fade out last 1s
      let alpha = 1
      if (age < 400) alpha = age / 400
      else if (age > 5000) alpha = 1 - (age - 5000) / 1000

      ctx.globalAlpha = alpha

      // Box background
      const boxW = Math.min(w * 0.7, 400)
      const boxH = 44
      const boxX = (w - boxW) / 2
      const boxY = h * 0.18 - boxH / 2 + progress * 15  // slight drift down

      ctx.fillStyle = 'rgba(0, 10, 0, 0.7)'
      ctx.fillRect(boxX, boxY, boxW, boxH)

      // ASCII border
      ctx.font = '10px ' + FONT
      ctx.fillStyle = ann.color
      ctx.textAlign = 'center'
      const borderLine = '+' + '-'.repeat(Math.floor(boxW / 6.5)) + '+'
      ctx.fillText(borderLine, w / 2, boxY + 2)
      ctx.fillText(borderLine, w / 2, boxY + boxH - 1)

      // Main text
      ctx.font = 'bold 14px ' + FONT
      ctx.fillStyle = ann.color
      ctx.fillText(ann.text, w / 2, boxY + 19)

      // Sub text
      ctx.font = '10px ' + FONT
      ctx.fillStyle = '#668866'
      ctx.fillText(ann.sub, w / 2, boxY + 34)

      ctx.globalAlpha = 1
    }

    // News ships flying across
    for (const ns of newsShips) {
      const age = now - ns.time
      if (age > 20000) continue

      // Update position
      ns.x += ns.speed

      // Skip if off screen
      if ((ns.speed > 0 && ns.x > w + 300) || (ns.speed < 0 && ns.x < -300)) continue

      const shipY = ns.y

      // Draw the ship + banner
      ctx.font = '10px ' + FONT
      ctx.textAlign = ns.speed > 0 ? 'left' : 'right'

      // Ship ASCII art (direction-dependent)
      const goingRight = ns.speed > 0
      const shipArt = goingRight ? '=>>' : '<<='
      const trail = goingRight ? '---' : '---'

      // Trail behind ship
      ctx.fillStyle = ns.color + '33' // very faint
      const trailX = goingRight ? ns.x - 4 : ns.x + 4
      ctx.textAlign = goingRight ? 'right' : 'left'
      ctx.fillText(trail.repeat(3), trailX, shipY)

      // Ship
      ctx.fillStyle = ns.color
      ctx.textAlign = 'center'
      ctx.font = '11px ' + FONT
      ctx.fillText(shipArt, ns.x, shipY)

      // Banner text (attached to ship, trailing behind)
      ctx.font = '9px ' + FONT
      ctx.fillStyle = ns.color + 'cc'
      const bannerX = goingRight ? ns.x + 22 : ns.x - 22
      ctx.textAlign = goingRight ? 'left' : 'right'

      // Banner background
      const textW = ctx.measureText(ns.text).width
      const bgX = goingRight ? bannerX - 3 : bannerX - textW - 3
      ctx.fillStyle = 'rgba(0, 8, 0, 0.6)'
      ctx.fillRect(bgX, shipY - 10, textW + 6, 14)

      // Banner text
      ctx.fillStyle = ns.color
      ctx.fillText(ns.text, bannerX, shipY)

      // Icon before text
      if (ns.icon) {
        ctx.fillStyle = ns.color + '88'
        const iconX = goingRight ? bannerX + textW + 6 : bannerX - textW - 6
        ctx.textAlign = 'center'
        ctx.fillText(ns.icon, iconX, shipY)
      }
    }

    // Ralph
    if (gameOver) {
      // Wreckage where Ralph was
      const rx = ralphXRef.current
      const ry = h * 0.91
      ctx.font = '10px ' + FONT
      ctx.fillStyle = '#442222'
      ctx.textAlign = 'center'
      const wreckFrame = Math.floor(now / 400) % 2
      if (wreckFrame === 0) {
        ctx.fillText(' .\\|/. ', rx, ry - 4)
        ctx.fillText(' /___\\ ', rx, ry + 8)
      } else {
        ctx.fillText(' ./|\\. ', rx, ry - 4)
        ctx.fillText(' \\___/ ', rx, ry + 8)
      }
      ctx.fillStyle = '#331111'
      ctx.fillText('R.I.P.', rx, ry + 22)

      // Game Over banner at top (not blocking the view)
      ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
      ctx.fillRect(0, h * 0.42, w, 50)
      ctx.font = 'bold 20px ' + FONT
      ctx.fillStyle = '#ff4444'
      ctx.textAlign = 'center'
      ctx.fillText('--- GAME OVER ---', w / 2, h * 0.42 + 22)
      ctx.font = '11px ' + FONT
      ctx.fillStyle = '#446644'
      ctx.fillText('[ CLICK TO RESPAWN ]', w / 2, h * 0.42 + 40)
    } else {
      // Alive Ralph
      const ralphVisible = ralphInvulnRef.current === 0 || Math.floor(now / 80) % 2 === 0
      if (ralphVisible) {
        const mood = ralphHitFlashRef.current > 0 ? 'sweating' as RalphMood : getRalphMood(changes)
        drawRalphAscii(ctx, ralphXRef.current, h * 0.91, mood, now, FONT, ralphHitFlashRef.current > 0)
      }
      // Hit flash overlay
      if (ralphHitFlashRef.current > 10) {
        ctx.globalAlpha = 0.15
        ctx.fillStyle = '#ff0000'
        ctx.fillRect(0, 0, w, h)
        ctx.globalAlpha = 1
      }
    }

    // Pause / Countdown overlay
    if (isPaused && countdownRef.current > 0) {
      // Countdown: semi-transparent overlay + big number
      ctx.fillStyle = 'rgba(0, 0, 0, 0.5)'
      ctx.fillRect(0, 0, w, h)

      const cd = countdownRef.current
      const pulse = 1 + Math.sin(now / 150) * 0.15
      ctx.font = `bold ${60 * pulse}px ${FONT}`
      ctx.fillStyle = cd === 1 ? '#44ff44' : cd === 2 ? '#ffaa44' : '#ff4444'
      ctx.textAlign = 'center'
      ctx.fillText(String(cd), w / 2, h / 2)

      ctx.font = '12px ' + FONT
      ctx.fillStyle = '#446644'
      ctx.fillText('GET READY', w / 2, h / 2 + 40)
    } else if (isPaused) {
      // Pure pause (waiting for visibility)
      ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
      ctx.fillRect(0, 0, w, h)

      ctx.font = 'bold 24px ' + FONT
      ctx.fillStyle = '#668866'
      ctx.textAlign = 'center'
      ctx.fillText('=== PAUSED ===', w / 2, h / 2)
    }

    // Controls
    ctx.font = '9px ' + FONT
    ctx.fillStyle = '#1a2a1a'
    ctx.textAlign = 'center'
    const controlText = gameOver ? '[ CLICK TO RESPAWN ]'
      : isPaused ? '[ RETURNING... ]'
      : '[<] [>] move    [SPACE] fire'
    ctx.fillText(controlText, w / 2, h - 4)

    rafRef.current = requestAnimationFrame(draw)
  }, [changes, gameOver, onHit, onRalphHit])

  useEffect(() => {
    const resize = () => {
      const canvas = canvasRef.current
      const container = containerRef.current
      if (!canvas || !container) return
      const cw = container.clientWidth
      const ch = container.clientHeight
      if (cw === 0 || ch === 0) return // hidden, skip
      canvas.width = cw
      canvas.height = ch
      if (ralphXRef.current === 0 || ralphXRef.current > cw) ralphXRef.current = cw / 2
    }
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [isVisible]) // re-run when visibility changes to pick up correct size

  useEffect(() => {
    rafRef.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(rafRef.current)
  }, [draw])

  return (
    <div ref={containerRef} className="flex-1 min-h-0 relative" tabIndex={0}>
      <canvas
        ref={canvasRef}
        onClick={gameOver ? onContinue : undefined}
        className={`outline-none ${gameOver ? 'cursor-pointer' : ''}`}
        tabIndex={0}
      />
    </div>
  )
}

function drawRalphAscii(ctx: CanvasRenderingContext2D, x: number, y: number, mood: RalphMood, now: number, font: string, isHit: boolean = false) {
  ctx.textAlign = 'center'

  // Engine flame (animated)
  const flicker = Math.floor(now / 60) % 3
  ctx.font = '10px ' + font
  ctx.fillStyle = flicker === 0 ? '#ffaa22' : flicker === 1 ? '#ff6622' : '#ffdd44'
  const flames = flicker === 0 ? '  \\/\\/' : flicker === 1 ? '  /\\/\\' : '  \\\\// '
  ctx.fillText(flames, x, y + 28)

  // Ship body
  const shipColor = isHit ? '#ff4444' : '#44ff88'
  ctx.font = '11px ' + font
  ctx.fillStyle = shipColor

  const ship = RALPH_SHIP
  for (let i = 0; i < ship.length; i++) {
    ctx.fillText(ship[i], x, y - 14 + i * 12)
  }

  // Face in cockpit
  ctx.font = '9px ' + font
  ctx.fillStyle = '#aaffaa'
  let face = 'o_o'
  switch (mood) {
    case 'sleeping': face = '-_-'; break
    case 'working': face = 'o_o'; break
    case 'multithreading': face = 'O_O'; break
    case 'celebrating': face = '^_^'; break
    case 'sweating': face = '>_<'; break
    case 'victory': face = '*_*'; break
  }
  ctx.fillText(face, x, y + 1)

  // Mood indicator
  ctx.font = '8px ' + font
  ctx.fillStyle = '#336633'
  switch (mood) {
    case 'sleeping': ctx.fillText('zzz', x + 30, y - 16); break
    case 'multithreading': ctx.fillText('!!', x + 30, y - 16); break
    case 'celebrating': ctx.fillText('\\o/', x + 30, y - 16); break
    case 'sweating': ctx.fillText('~.~', x + 30, y - 16); break
    case 'victory': ctx.fillText('GG!', x + 30, y - 16); break
  }

  // Label
  ctx.font = '8px ' + font
  ctx.fillStyle = '#1a3a1a'
  ctx.fillText('RALPH', x, y + 40)
}
