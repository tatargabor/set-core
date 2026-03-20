import { useState, useEffect } from 'react'
import { getScoreboard, type ScoreboardEntry } from '../../lib/api'
import { ACHIEVEMENTS } from '../../lib/battleScoring'

const rarityColor: Record<string, string> = {
  common: 'text-neutral-400',
  uncommon: 'text-green-400',
  rare: 'text-blue-400',
  epic: 'text-purple-400',
  legendary: 'text-yellow-400',
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`
  return String(n)
}

export default function Scoreboard() {
  const [entries, setEntries] = useState<ScoreboardEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = () => {
      getScoreboard(20)
        .then(d => setEntries(d.entries))
        .catch(() => {})
        .finally(() => setLoading(false))
    }
    load()
    const iv = setInterval(load, 30000)
    return () => clearInterval(iv)
  }, [])

  if (loading) return null

  if (entries.length === 0) {
    return (
      <div className="text-center text-neutral-600 text-xs py-2">
        No scores yet. Play to submit!
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <div className="text-[9px] text-neutral-500 uppercase tracking-wider font-medium px-1">
        Scoreboard
      </div>
      <div className="space-y-0.5">
        {entries.map((e, i) => {
          const medal = i === 0 ? '\u{1F947}' : i === 1 ? '\u{1F948}' : i === 2 ? '\u{1F949}' : `${i + 1}.`
          const topAchievements = e.achievements
            .map(id => ACHIEVEMENTS.find(a => a.id === id))
            .filter(Boolean)
            .sort((a, b) => {
              const order = ['legendary', 'epic', 'rare', 'uncommon', 'common']
              return order.indexOf(a!.rarity) - order.indexOf(b!.rarity)
            })
            .slice(0, 3)

          return (
            <div
              key={`${e.player}-${e.project}`}
              className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs ${
                i < 3 ? 'bg-neutral-900/80 border border-neutral-800' : 'bg-neutral-900/30'
              }`}
            >
              <span className="w-6 text-center shrink-0 text-neutral-500">{medal}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-neutral-200 truncate">{e.player}</span>
                  <span className="text-[9px] text-neutral-600 truncate">{e.project}</span>
                </div>
                <div className="flex items-center gap-2 text-[9px] text-neutral-500">
                  <span>{e.changes_done}/{e.total_changes} changes</span>
                  <span>{formatTokens(e.total_tokens)} tok</span>
                  <span>{timeAgo(e.timestamp)}</span>
                  {topAchievements.map(a => (
                    <span key={a!.id} className={rarityColor[a!.rarity]} title={a!.name}>
                      {a!.emoji}
                    </span>
                  ))}
                </div>
              </div>
              <span className="font-mono font-bold text-neutral-100 shrink-0">
                {e.score.toLocaleString()}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
