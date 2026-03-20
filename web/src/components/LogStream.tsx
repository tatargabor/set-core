import { useRef, useEffect, useState } from 'react'

interface Props {
  lines: string[]
}

function lineColor(line: string): string {
  if (line.includes('ERROR')) return 'text-red-400'
  if (line.includes('WARN')) return 'text-yellow-400'
  if (line.includes('REPLAN')) return 'text-cyan-400'
  if (line.includes('CHECKPOINT')) return 'text-yellow-300'
  return 'text-neutral-400'
}

export default function LogStream({ lines }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines, autoScroll])

  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }

  return (
    <div className="relative h-full flex flex-col">
      <div className="flex items-center justify-between px-3 py-1 border-b border-neutral-800 bg-neutral-900/50">
        <span className="text-xs text-neutral-500 font-medium">Log</span>
        <span className="text-xs text-neutral-600">{lines.length} lines</span>
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-auto p-2 text-xs leading-5"
      >
        {lines.map((line, i) => (
          <div key={i} className={lineColor(line)}>
            {line}
          </div>
        ))}
      </div>
      {!autoScroll && (
        <button
          onClick={() => {
            setAutoScroll(true)
            if (containerRef.current) {
              containerRef.current.scrollTop = containerRef.current.scrollHeight
            }
          }}
          className="absolute bottom-3 right-3 px-2 py-1 text-xs bg-neutral-800 text-neutral-300 rounded hover:bg-neutral-700"
        >
          Jump to bottom
        </button>
      )}
    </div>
  )
}
