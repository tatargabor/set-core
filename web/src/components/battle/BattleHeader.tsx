import type { ScoreState } from '../../lib/battleScoring'

interface Props {
  state: ScoreState
}

export default function BattleHeader({ state }: Props) {
  const hearts = Array.from({ length: 3 }, (_, i) => i < state.lives)
  const isNewHigh = state.score > 0 && state.score >= state.highScore

  return (
    <div className="flex items-center gap-4 px-4 py-2 border-b border-neutral-800 bg-neutral-900/80 shrink-0">
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-neutral-500 uppercase tracking-wider">Score</span>
        <span className="text-sm font-mono font-bold text-neutral-100">{state.score.toLocaleString()}</span>
        {isNewHigh && (
          <span className="text-[9px] font-bold text-yellow-400 animate-pulse">NEW HIGH!</span>
        )}
      </div>

      <div className="flex items-center gap-1">
        <span className="text-[10px] text-neutral-500 uppercase tracking-wider">Hi</span>
        <span className="text-xs font-mono text-neutral-400">{state.highScore.toLocaleString()}</span>
      </div>

      {state.multiplier > 1 && (
        <span className="text-xs font-bold text-cyan-400">x{state.multiplier}</span>
      )}

      <div className="flex gap-0.5 ml-auto">
        {hearts.map((alive, i) => (
          <span key={i} className={`text-sm ${alive ? 'text-red-500' : 'text-neutral-700'}`}>
            {alive ? '\u2665' : '\u2661'}
          </span>
        ))}
      </div>
    </div>
  )
}
