import { ACHIEVEMENTS } from '../../lib/battleScoring'

interface Props {
  unlocked: string[]
}

const rarityColor: Record<string, string> = {
  common: 'border-neutral-600',
  uncommon: 'border-green-700',
  rare: 'border-blue-700',
  epic: 'border-purple-700',
  legendary: 'border-yellow-600',
}

export default function AchievementBar({ unlocked }: Props) {
  return (
    <div className="flex flex-wrap gap-1 px-3 py-2">
      {ACHIEVEMENTS.map(a => {
        const isUnlocked = unlocked.includes(a.id)
        return (
          <div
            key={a.id}
            title={isUnlocked ? `${a.name}: ${a.description}` : '???'}
            className={`w-7 h-7 flex items-center justify-center rounded border text-xs cursor-default transition-all ${
              isUnlocked
                ? `${rarityColor[a.rarity]} bg-neutral-800 opacity-100`
                : 'border-neutral-800 bg-neutral-900 opacity-40'
            }`}
          >
            {isUnlocked ? a.emoji : '\u{1F512}'}
          </div>
        )
      })}
    </div>
  )
}
