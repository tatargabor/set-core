import { useEffect, useState } from 'react'
import type { AchievementDef } from '../../lib/battleScoring'

const rarityBg: Record<string, string> = {
  common: 'bg-neutral-800 border-neutral-600',
  uncommon: 'bg-green-950 border-green-700',
  rare: 'bg-blue-950 border-blue-700',
  epic: 'bg-purple-950 border-purple-700',
  legendary: 'bg-yellow-950 border-yellow-600',
}

const rarityLabel: Record<string, string> = {
  common: 'text-neutral-400',
  uncommon: 'text-green-400',
  rare: 'text-blue-400',
  epic: 'text-purple-400',
  legendary: 'text-yellow-400',
}

interface Props {
  queue: AchievementDef[]
  onDismiss: () => void
}

export default function AchievementPopup({ queue, onDismiss }: Props) {
  const [visible, setVisible] = useState(false)
  const current = queue[0]

  useEffect(() => {
    if (!current) return
    setVisible(true)
    const timer = setTimeout(() => {
      setVisible(false)
      setTimeout(onDismiss, 300)
    }, 3000)
    return () => clearTimeout(timer)
  }, [current, onDismiss])

  if (!current) return null

  return (
    <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 transition-all duration-300 ${
      visible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'
    }`}>
      <div className={`rounded-lg border px-5 py-3 shadow-2xl ${rarityBg[current.rarity]}`}>
        <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Achievement Unlocked!</div>
        <div className="flex items-center gap-2">
          <span className="text-2xl">{current.emoji}</span>
          <div>
            <div className="text-sm font-semibold text-neutral-100">{current.name}</div>
            <div className="text-[11px] text-neutral-400">{current.description}</div>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-1">
          {current.bonus > 0 && (
            <span className="text-xs font-mono text-green-400">+{current.bonus}</span>
          )}
          <span className={`text-[9px] uppercase tracking-wider font-medium ${rarityLabel[current.rarity]}`}>
            {current.rarity}
          </span>
        </div>
      </div>
    </div>
  )
}
