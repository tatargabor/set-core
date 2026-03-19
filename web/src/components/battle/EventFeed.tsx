export interface BattleEvent {
  time: string
  emoji: string
  text: string
  points?: number
}

interface Props {
  events: BattleEvent[]
}

export default function EventFeed({ events }: Props) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-1.5 text-[9px] text-neutral-600 uppercase tracking-wider font-medium border-b border-neutral-800">
        Live Feed
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-1 space-y-0.5">
        {events.length === 0 && (
          <div className="text-[10px] text-neutral-600 py-2">Waiting for action...</div>
        )}
        {events.map((e, i) => (
          <div key={i} className="flex items-start gap-1.5 text-[10px]">
            <span className="text-neutral-600 font-mono shrink-0">{e.time}</span>
            <span>{e.emoji}</span>
            <span className="text-neutral-300 flex-1">{e.text}</span>
            {e.points != null && e.points !== 0 && (
              <span className={`font-mono shrink-0 ${e.points > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {e.points > 0 ? '+' : ''}{e.points}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
