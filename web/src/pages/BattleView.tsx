import { useState, useCallback, useRef, useEffect } from 'react'
import type { ChangeInfo } from '../lib/api'
import { signScore, submitScore } from '../lib/api'
import { detectTransitions, detectEvents, type ChangeEvent } from '../lib/battleTransitions'
import { createScoreState, processTransition, saveScore, loadScore, type ScoreState, type AchievementDef } from '../lib/battleScoring'
import type { BattleEvent } from '../components/battle/EventFeed'
import BattleHeader from '../components/battle/BattleHeader'
import BattleCanvas, { type Announcement, type NewsShip } from '../components/battle/BattleCanvas'
import AchievementBar from '../components/battle/AchievementBar'
import AchievementPopup from '../components/battle/AchievementPopup'
import Scoreboard from '../components/battle/Scoreboard'

interface Props {
  project: string
  changes: ChangeInfo[]
  isVisible: boolean
}

function timeStr(): string {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

function newsShipForEvent(ev: ChangeEvent): { icon: string; shipText: string; shipColor: string } {
  const short = ev.name.length > 14 ? ev.name.slice(0, 12) + '..' : ev.name
  switch (ev.type) {
    case 'new_session':
      return { icon: '++', shipText: `${short}: ${ev.detail}`, shipColor: '#66aaff' }
    case 'tokens_milestone':
      return { icon: '$$', shipText: `${short}: ${ev.detail}`, shipColor: '#ffaa44' }
    case 'iteration':
      return { icon: '>>', shipText: `${short}: ${ev.detail}`, shipColor: '#88cc88' }
    default:
      return { icon: '--', shipText: `${short}: ${ev.detail}`, shipColor: '#668866' }
  }
}

function newsShipForTransition(name: string, to: string): { icon: string; shipText: string; shipColor: string } {
  const short = name.length > 18 ? name.slice(0, 16) + '..' : name
  switch (to) {
    case 'dispatched':
      return { icon: '>>', shipText: `NEW SESSION: ${short}`, shipColor: '#4488ff' }
    case 'running':
    case 'implementing':
      return { icon: '>>', shipText: `IMPLEMENTING: ${short}`, shipColor: '#44ff88' }
    case 'verifying':
      return { icon: '??', shipText: `VERIFY GATE: ${short}`, shipColor: '#44ddff' }
    case 'failed':
    case 'verify-failed':
      return { icon: '!!', shipText: `FAILED: ${short}`, shipColor: '#ff4444' }
    case 'done':
    case 'completed':
      return { icon: 'OK', shipText: `DONE: ${short}`, shipColor: '#44ff44' }
    case 'merged':
      return { icon: '<<', shipText: `MERGED: ${short}`, shipColor: '#aa88ff' }
    case 'stalled':
      return { icon: '??', shipText: `STALLED: ${short}`, shipColor: '#ffaa00' }
    default:
      return { icon: '--', shipText: `${short}: ${to}`, shipColor: '#668866' }
  }
}

function announceTransition(name: string, from: string, to: string): { text: string; sub: string; color: string } {
  const short = name.length > 20 ? name.slice(0, 18) + '..' : name
  switch (to) {
    case 'dispatched':
      return { text: `>>> ${short} DISPATCHED <<<`, sub: 'Agent deployed to worktree', color: '#44aaff' }
    case 'running':
    case 'implementing':
      return { text: `[[ ${short} RUNNING ]]`, sub: from === 'failed' ? 'Retry attempt started' : 'Implementation in progress', color: '#44ff88' }
    case 'verifying':
      return { text: `=== VERIFY: ${short} ===`, sub: 'Running build + test + review gates', color: '#44ddff' }
    case 'failed':
    case 'verify-failed':
      return { text: `!!! ${short} FAILED !!!`, sub: to === 'verify-failed' ? 'Verify gate rejected' : 'Agent crashed or timed out', color: '#ff4444' }
    case 'done':
    case 'completed':
      return { text: `*** ${short} COMPLETE ***`, sub: 'All gates passed - ready to merge', color: '#44ff44' }
    case 'merged':
      return { text: `<<< ${short} MERGED >>>`, sub: 'Changes merged to main branch', color: '#aa88ff' }
    case 'stalled':
      return { text: `??? ${short} STALLED ???`, sub: 'No activity detected', color: '#ffaa00' }
    case 'skipped':
    case 'skip_merged':
      return { text: `--- ${short} SKIPPED ---`, sub: 'Change bypassed', color: '#666666' }
    default:
      return { text: `${short}: ${from} -> ${to}`, sub: 'Status changed', color: '#888888' }
  }
}

function narrateTransition(name: string, to: string): { emoji: string; text: string } {
  switch (to) {
    case 'dispatched': return { emoji: '\u{1F6F8}', text: `${name} DISPATCHED` }
    case 'running':
    case 'implementing': return { emoji: '\u{1F680}', text: `${name} entering atmosphere` }
    case 'verifying': return { emoji: '\u{1F50D}', text: `${name} SCANNING...` }
    case 'failed':
    case 'verify-failed': return { emoji: '\u{1F4A5}', text: `${name} EXPLODED` }
    case 'done':
    case 'merged':
    case 'completed': return { emoji: '\u2705', text: `${name} LANDED` }
    case 'stalled': return { emoji: '\u26A0\uFE0F', text: `${name} stalled` }
    default: return { emoji: '\u{1F504}', text: `${name} \u2192 ${to}` }
  }
}

function PlayerNameInput() {
  const [name, setName] = useState(() => localStorage.getItem('set-battle-player') || '')
  const [editing, setEditing] = useState(!name)

  const save = () => {
    const trimmed = name.trim().slice(0, 20) || 'Anonymous'
    localStorage.setItem('set-battle-player', trimmed)
    setName(trimmed)
    setEditing(false)
  }

  if (!editing) {
    return (
      <button
        onClick={() => setEditing(true)}
        className="mt-4 text-xs text-neutral-500 hover:text-neutral-300 transition-colors"
      >
        Player: <span className="font-mono text-neutral-300">{name}</span> (click to change)
      </button>
    )
  }

  return (
    <div className="mt-4 flex items-center gap-2">
      <span className="text-xs text-neutral-500">Player name:</span>
      <input
        type="text"
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && save()}
        maxLength={20}
        placeholder="Your name"
        className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 w-32 focus:outline-none focus:border-neutral-500"
        autoFocus
      />
      <button
        onClick={save}
        className="px-2 py-1 text-xs bg-neutral-800 text-neutral-300 rounded hover:bg-neutral-700"
      >
        Save
      </button>
    </div>
  )
}

export default function BattleView({ project, changes, isVisible }: Props) {
  const prevChangesRef = useRef<ChangeInfo[]>([])
  const [scoreState, setScoreState] = useState<ScoreState>(() => {
    const saved = loadScore(project)
    const s = createScoreState()
    s.highScore = saved.highScore
    s.achievements = [...saved.achievements]
    return s
  })
  const [_events, setEvents] = useState<BattleEvent[]>([])
  const [achievementQueue, setAchievementQueue] = useState<AchievementDef[]>([])
  const [gameOver, setGameOver] = useState(false)
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [newsShips, setNewsShips] = useState<NewsShip[]>([])
  const newsIdRef = useRef(0)

  // Detect transitions and update score
  useEffect(() => {
    const prev = prevChangesRef.current
    prevChangesRef.current = changes

    if (prev.length === 0 && changes.length > 0) {
      // Initial load — add "battle started" event
      setEvents(e => [{ time: timeStr(), emoji: '\u{1F3AE}', text: 'Battle started!' }, ...e].slice(0, 20))
      return
    }

    const transitions = detectTransitions(prev, changes)
    if (transitions.length === 0) return

    // Generate center announcements
    const now = performance.now()
    const newAnnouncements: Announcement[] = transitions.map(t => {
      const { text, sub, color } = announceTransition(t.name, t.from, t.to)
      return { text, sub, color, time: now }
    })
    if (newAnnouncements.length > 0) {
      newAnnouncements.forEach((a, i) => { a.time += i * 800 })
      setAnnouncements(prev => [...prev, ...newAnnouncements].filter(a => now - a.time < 8000))
    }

    // Detect non-status events (sessions, tokens, iterations)
    const changeEvents = detectEvents(prev, changes)

    // Generate news ships for status transitions
    const transitionShips: NewsShip[] = transitions.map((t, i) => {
      const { icon, shipText, shipColor } = newsShipForTransition(t.name, t.to)
      const goRight = i % 2 === 0
      return {
        id: newsIdRef.current++,
        text: shipText,
        color: shipColor,
        y: 50 + (i * 25) % 80 + Math.random() * 30,
        speed: goRight ? 1.5 + Math.random() : -(1.5 + Math.random()),
        x: goRight ? -200 : (typeof window !== 'undefined' ? window.innerWidth + 200 : 1200),
        time: now + i * 400,
        icon,
      }
    })

    // Generate news ships for change events (sessions, milestones)
    const eventShips: NewsShip[] = changeEvents.map((ev, i) => {
      const { icon, shipText, shipColor } = newsShipForEvent(ev)
      const goRight = (transitions.length + i) % 2 === 0
      return {
        id: newsIdRef.current++,
        text: shipText,
        color: shipColor,
        y: 60 + ((transitions.length + i) * 25) % 80 + Math.random() * 20,
        speed: goRight ? 1.2 + Math.random() * 0.5 : -(1.2 + Math.random() * 0.5),
        x: goRight ? -200 : (typeof window !== 'undefined' ? window.innerWidth + 200 : 1200),
        time: now + (transitions.length + i) * 400,
        icon,
      }
    })

    // Also add events to the feed
    for (const ev of changeEvents) {
      const { icon, shipText } = newsShipForEvent(ev)
      setEvents(e => [{ time: timeStr(), emoji: icon, text: shipText, points: undefined }, ...e].slice(0, 20))
    }

    const allNewShips = [...transitionShips, ...eventShips]
    if (allNewShips.length > 0) {
      setNewsShips(prev => [...prev, ...allNewShips].filter(s => now - s.time < 25000))
    }

    setScoreState(prevState => {
      const newState = { ...prevState }
      const newEvents: BattleEvent[] = []
      const newAchievements: AchievementDef[] = []

      for (const t of transitions) {
        const scoreEvents = processTransition(newState, t, changes)
        const narration = narrateTransition(t.name, t.to)

        // Main transition event
        const totalPoints = scoreEvents.reduce((sum, e) => sum + e.points, 0)
        newEvents.push({
          time: timeStr(),
          emoji: narration.emoji,
          text: narration.text,
          points: totalPoints !== 0 ? totalPoints : undefined,
        })

        // Achievement events
        for (const se of scoreEvents) {
          if (se.achievement) {
            newAchievements.push(se.achievement)
            newEvents.push({
              time: timeStr(),
              emoji: '\u{1F3C6}',
              text: `ACHIEVEMENT: ${se.achievement.name}`,
              points: se.achievement.bonus,
            })
          }
        }
      }

      if (newEvents.length > 0) {
        setEvents(e => [...newEvents, ...e].slice(0, 20))
      }
      if (newAchievements.length > 0) {
        setAchievementQueue(q => [...q, ...newAchievements])
      }

      // Game over check
      if (newState.lives <= 0) {
        setGameOver(true)
      }

      saveScore(project, newState)
      return newState
    })
  }, [changes, project])

  const handleContinue = useCallback(() => {
    setGameOver(false)
    setScoreState(s => ({ ...s, lives: 3 }))
  }, [])

  const handleDismissAchievement = useCallback(() => {
    setAchievementQueue(q => q.slice(1))
  }, [])

  const handleHit = useCallback((changeName: string, points: number, combo: number) => {
    setScoreState(s => {
      const newState = { ...s, score: s.score + points }
      if (newState.score > newState.highScore) newState.highScore = newState.score
      saveScore(project, newState)
      return newState
    })
    const comboText = combo >= 2 ? ` (x${combo} combo!)` : ''
    setEvents(e => [{
      time: timeStr(),
      emoji: combo >= 3 ? '\u{1F525}' : '\u{1F4AB}',
      text: `SHOT ${changeName}!${comboText}`,
      points,
    }, ...e].slice(0, 20))
  }, [project])

  const handleRalphHit = useCallback(() => {
    setScoreState(s => {
      const newState = { ...s, lives: Math.max(0, s.lives - 1) }
      if (newState.lives <= 0) setGameOver(true)
      saveScore(project, newState)
      return newState
    })
    setEvents(e => [{
      time: timeStr(),
      emoji: '\u{1F4A5}',
      text: 'RALPH GOT HIT!',
      points: 0,
    }, ...e].slice(0, 20))
  }, [project])

  const submittedRef = useRef(false)
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'submitting' | 'done' | 'error'>('idle')
  const [submitRank, setSubmitRank] = useState<number | null>(null)

  const doSubmit = useCallback(() => {
    if (submitStatus === 'submitting') return
    setSubmitStatus('submitting')

    const changesDone = changes.filter(c => ['done', 'merged', 'completed'].includes(c.status)).length
    const totalTokens = changes.reduce((s, c) => s + (c.input_tokens ?? 0) + (c.output_tokens ?? 0), 0)
    const player = localStorage.getItem('set-battle-player') || 'Anonymous'

    signScore(project, scoreState.score, changesDone, totalTokens)
      .then(sig => submitScore({
        player,
        project,
        score: scoreState.score,
        changes_done: changesDone,
        total_changes: changes.length,
        total_tokens: totalTokens,
        achievements: scoreState.achievements,
        signature: sig,
      }))
      .then(res => {
        setSubmitStatus('done')
        setSubmitRank(res.rank ?? null)
      })
      .catch(() => setSubmitStatus('error'))
  }, [changes, project, scoreState, submitStatus])

  // Auto-submit when all changes done
  useEffect(() => {
    if (submittedRef.current || changes.length === 0 || scoreState.score === 0) return
    const allDone = changes.every(c => ['done', 'merged', 'completed', 'skip_merged', 'skipped'].includes(c.status))
    if (!allDone) return
    submittedRef.current = true
    doSubmit()
  }, [changes, scoreState.score, doSubmit])

  const hasChanges = changes.length > 0

  return (
    <div className="flex flex-col h-full">
      <BattleHeader
        state={scoreState}
        onSubmitScore={doSubmit}
        submitStatus={submitStatus}
        submitRank={submitRank}
      />

      {!hasChanges ? (
        <div className="flex-1 overflow-auto">
          <div className="flex flex-col items-center justify-center text-neutral-500 py-8">
            <span className="text-4xl mb-4">(-_-) zzz</span>
            <span className="text-sm">Waiting for orchestration...</span>
            {scoreState.highScore > 0 && (
              <span className="text-xs text-neutral-600 mt-2">High Score: {scoreState.highScore.toLocaleString()}</span>
            )}
            <div className="mt-4">
              <AchievementBar unlocked={scoreState.achievements} />
            </div>

            {/* Player name */}
            <PlayerNameInput />

            {/* Scoreboard */}
            <div className="mt-6 w-full max-w-md px-4">
              <Scoreboard />
            </div>
          </div>
        </div>
      ) : (
        <>
          <BattleCanvas
            changes={changes}
            gameOver={gameOver}
            announcements={announcements}
            newsShips={newsShips}
            isVisible={isVisible}
            onContinue={handleContinue}
            onHit={handleHit}
            onRalphHit={handleRalphHit}
          />

          <div className="shrink-0 border-t border-neutral-800 px-1 py-0.5">
            <AchievementBar unlocked={scoreState.achievements} />
          </div>
        </>
      )}

      <AchievementPopup queue={achievementQueue} onDismiss={handleDismissAchievement} />
    </div>
  )
}
