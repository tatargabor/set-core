import { useRef, useEffect, useCallback } from 'react'
import type { ChangeInfo } from '../../lib/api'
import { SpriteManager, getZoneY } from '../../lib/battleSprites'

interface Props {
  changes: ChangeInfo[]
  gameOver: boolean
  onContinue: () => void
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

export default function BattleCanvas({ changes, gameOver, onContinue }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const spriteManagerRef = useRef(new SpriteManager())
  const rafRef = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const w = canvas.width
    const h = canvas.height
    const now = performance.now()
    const sm = spriteManagerRef.current

    sm.update(changes, w, h, now)

    // Clear
    ctx.fillStyle = '#0a0a0a'
    ctx.fillRect(0, 0, w, h)

    // Zone lines
    const zones: Array<{ zone: 'orbit' | 'atmosphere' | 'ground'; label: string }> = [
      { zone: 'orbit', label: 'ORBIT' },
      { zone: 'atmosphere', label: 'ATMOSPHERE' },
      { zone: 'ground', label: 'GROUND' },
    ]

    for (const z of zones) {
      const zy = getZoneY(z.zone, h)
      ctx.strokeStyle = '#262626'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 4])
      ctx.beginPath()
      ctx.moveTo(0, zy.min - 5)
      ctx.lineTo(w, zy.min - 5)
      ctx.stroke()
      ctx.setLineDash([])

      ctx.fillStyle = '#404040'
      ctx.font = '9px monospace'
      ctx.fillText(z.label, 8, zy.min - 10)
    }

    // Draw sprites
    for (const s of sm.sprites.values()) {
      const baseSize = 16 * s.size
      ctx.font = `${baseSize}px serif`
      ctx.textAlign = 'center'

      // Sprite emoji
      let emoji = '\u{1F47E}' // 👾
      if (s.zone === 'atmosphere') {
        if (s.status === 'failed' || s.status === 'verify-failed') {
          emoji = s.animFrame % 20 < 10 ? '\u{1F4A5}' : '\u{1F527}' // 💥 / 🔧
        } else if (s.status === 'verifying') {
          emoji = '\u{1F50D}' // 🔍
        } else if (s.status === 'stalled') {
          emoji = s.animFrame % 30 < 15 ? '\u26A0\uFE0F' : '' // ⚠️ blink
        } else {
          emoji = '\u{1F6F8}' // 🛸
        }
      } else if (s.zone === 'ground') {
        emoji = '\u2705' // ✅
      }

      // Orbit float animation
      let drawY = s.y
      if (s.zone === 'orbit') {
        drawY += Math.sin(now / 1000 + s.x) * 5
      }

      if (emoji) ctx.fillText(emoji, s.x, drawY)

      // Name label
      ctx.font = '9px monospace'
      ctx.fillStyle = '#a3a3a3'
      const shortName = s.name.length > 14 ? s.name.slice(0, 12) + '..' : s.name
      ctx.fillText(shortName, s.x, drawY + baseSize * 0.7)

      // Progress bar for running
      if (s.zone === 'atmosphere' && s.progress > 0 && !['failed', 'verify-failed', 'stalled'].includes(s.status)) {
        const barW = 50
        const barH = 4
        const barX = s.x - barW / 2
        const barY = drawY + baseSize * 0.85

        ctx.fillStyle = '#262626'
        ctx.fillRect(barX, barY, barW, barH)
        ctx.fillStyle = '#22c55e'
        ctx.fillRect(barX, barY, barW * s.progress, barH)

        // Tok/s
        if (s.tokensPerSec > 0) {
          ctx.fillStyle = '#525252'
          ctx.font = '8px monospace'
          ctx.fillText(`${s.tokensPerSec} t/s`, s.x, barY + 12)
        }
      }
    }

    // Draw Ralph
    const ralph = getRalphMood(changes)
    drawRalph(ctx, w / 2, h * 0.92, ralph, now)

    // Game Over overlay
    if (gameOver) {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'
      ctx.fillRect(0, 0, w, h)

      ctx.fillStyle = '#ef4444'
      ctx.font = 'bold 32px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('GAME OVER', w / 2, h / 2 - 20)

      ctx.fillStyle = '#a3a3a3'
      ctx.font = '14px monospace'
      ctx.fillText('Click to continue', w / 2, h / 2 + 20)
    }

    rafRef.current = requestAnimationFrame(draw)
  }, [changes, gameOver])

  // Resize
  useEffect(() => {
    const resize = () => {
      const canvas = canvasRef.current
      const container = containerRef.current
      if (!canvas || !container) return
      const dpr = window.devicePixelRatio || 1
      canvas.width = container.clientWidth * dpr
      canvas.height = container.clientHeight * dpr
      canvas.style.width = `${container.clientWidth}px`
      canvas.style.height = `${container.clientHeight}px`
      const ctx = canvas.getContext('2d')
      if (ctx) ctx.scale(dpr, dpr)
      // Logical size for drawing
      canvas.width = container.clientWidth
      canvas.height = container.clientHeight
    }
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])

  // Animation loop
  useEffect(() => {
    rafRef.current = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(rafRef.current)
  }, [draw])

  return (
    <div ref={containerRef} className="flex-1 min-h-0 relative">
      <canvas
        ref={canvasRef}
        onClick={gameOver ? onContinue : undefined}
        className={gameOver ? 'cursor-pointer' : ''}
      />
    </div>
  )
}

function drawRalph(ctx: CanvasRenderingContext2D, x: number, y: number, mood: RalphMood, _now: number) {
  ctx.textAlign = 'center'

  // Body
  ctx.fillStyle = '#525252'
  ctx.fillRect(x - 12, y - 8, 24, 16)

  // Head
  ctx.fillStyle = '#737373'
  ctx.beginPath()
  ctx.arc(x, y - 14, 10, 0, Math.PI * 2)
  ctx.fill()

  // Face
  ctx.font = '10px monospace'
  ctx.fillStyle = '#e5e5e5'
  switch (mood) {
    case 'sleeping':
      ctx.fillText('-_-', x, y - 12)
      ctx.fillStyle = '#525252'
      ctx.font = '8px monospace'
      ctx.fillText('zzz', x + 14, y - 22)
      break
    case 'working':
      ctx.fillText('o_o', x, y - 12)
      ctx.fillStyle = '#facc15'
      ctx.font = '8px monospace'
      ctx.fillText('\u26A1', x + 14, y - 18)
      break
    case 'multithreading':
      ctx.fillText('O_O', x, y - 12)
      ctx.fillStyle = '#facc15'
      ctx.font = '8px monospace'
      ctx.fillText('\u26A1\u26A1\u26A1', x + 16, y - 18)
      // Extra arms
      ctx.strokeStyle = '#525252'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(x - 12, y - 4)
      ctx.lineTo(x - 24, y - 12)
      ctx.moveTo(x + 12, y - 4)
      ctx.lineTo(x + 24, y - 12)
      ctx.stroke()
      break
    case 'celebrating':
      ctx.fillText('^_^', x, y - 12)
      ctx.font = '10px serif'
      ctx.fillText('\u{1F389}', x + 16, y - 16)
      break
    case 'sweating':
      ctx.fillText('>_<', x, y - 12)
      ctx.fillStyle = '#3b82f6'
      ctx.font = '8px serif'
      ctx.fillText('\u{1F4A6}', x + 14, y - 16)
      break
    case 'victory':
      ctx.fillText('\u2605_\u2605', x, y - 12)
      ctx.font = '10px serif'
      ctx.fillText('\u{1F3C6}', x + 16, y - 16)
      break
  }

  // Label
  ctx.fillStyle = '#404040'
  ctx.font = '8px monospace'
  ctx.fillText('RALPH', x, y + 16)
}
