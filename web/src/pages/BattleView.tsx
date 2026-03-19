import { useState, useCallback, useRef, useEffect } from 'react'
import type { ChangeInfo } from '../lib/api'
import { detectTransitions } from '../lib/battleTransitions'
import { createScoreState, processTransition, saveScore, loadScore, type ScoreState, type AchievementDef } from '../lib/battleScoring'
import BattleHeader from '../components/battle/BattleHeader'
import BattleCanvas from '../components/battle/BattleCanvas'
import EventFeed, { type BattleEvent } from '../components/battle/EventFeed'
import AchievementBar from '../components/battle/AchievementBar'
import AchievementPopup from '../components/battle/AchievementPopup'

interface Props {
  project: string
  changes: ChangeInfo[]
}

function timeStr(): string {
  const d = new Date()
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
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

export default function BattleView({ project, changes }: Props) {
  const prevChangesRef = useRef<ChangeInfo[]>([])
  const [scoreState, setScoreState] = useState<ScoreState>(() => {
    const saved = loadScore(project)
    const s = createScoreState()
    s.highScore = saved.highScore
    s.achievements = [...saved.achievements]
    return s
  })
  const [events, setEvents] = useState<BattleEvent[]>([])
  const [achievementQueue, setAchievementQueue] = useState<AchievementDef[]>([])
  const [gameOver, setGameOver] = useState(false)

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

  const hasChanges = changes.length > 0

  return (
    <div className="flex flex-col h-full">
      <BattleHeader state={scoreState} />

      {!hasChanges ? (
        <div className="flex-1 flex flex-col items-center justify-center text-neutral-500">
          <span className="text-4xl mb-4">(-_-) zzz</span>
          <span className="text-sm">Waiting for orchestration...</span>
          {scoreState.highScore > 0 && (
            <span className="text-xs text-neutral-600 mt-2">High Score: {scoreState.highScore.toLocaleString()}</span>
          )}
          <div className="mt-4">
            <AchievementBar unlocked={scoreState.achievements} />
          </div>
        </div>
      ) : (
        <>
          <BattleCanvas
            changes={changes}
            gameOver={gameOver}
            onContinue={handleContinue}
          />

          <div className="shrink-0 border-t border-neutral-800 flex flex-col md:flex-row" style={{ maxHeight: '30%' }}>
            <div className="flex-1 border-r border-neutral-800 overflow-hidden">
              <EventFeed events={events} />
            </div>
            <div className="shrink-0 border-t md:border-t-0 border-neutral-800">
              <AchievementBar unlocked={scoreState.achievements} />
            </div>
          </div>
        </>
      )}

      <AchievementPopup queue={achievementQueue} onDismiss={handleDismissAchievement} />
    </div>
  )
}
