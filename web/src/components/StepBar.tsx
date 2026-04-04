interface Props {
  current_step?: string
}

const steps = [
  { key: 'planning', label: 'P', title: 'Planning (artifact creation)' },
  { key: 'implementing', label: 'I', title: 'Implementing (tasks)' },
  { key: 'fixing', label: 'F', title: 'Fixing (gate retry)' },
  { key: 'merging', label: 'M', title: 'Merging (integration + ff-only)' },
  { key: 'archiving', label: 'A', title: 'Archiving (spec sync)' },
]

// Order for "completed" logic — steps before current are green
const stepOrder = ['planning', 'implementing', 'fixing', 'integrating', 'merging', 'archiving', 'done']

const stepStyle: Record<string, string> = {
  completed: 'bg-green-900 text-green-300',
  current: 'bg-blue-800 text-blue-200 animate-pulse',
  fixing: 'bg-amber-900 text-amber-300 animate-pulse',
  pending: 'bg-neutral-800 text-neutral-600',
}

function getStepStatus(stepKey: string, currentStep: string | undefined): string {
  if (!currentStep) return 'pending'

  // "integrating" maps to before "merging" visually
  const currentIdx = stepOrder.indexOf(currentStep)
  const stepIdx = stepOrder.indexOf(stepKey)

  // "fixing" is special — only shows as active, never "completed"
  if (stepKey === 'fixing') {
    return currentStep === 'fixing' ? 'fixing' : 'pending'
  }

  if (stepIdx < currentIdx) return 'completed'
  if (stepKey === currentStep) return 'current'
  // "integrating" shows "merging" as current
  if (stepKey === 'merging' && currentStep === 'integrating') return 'current'
  return 'pending'
}

export default function StepBar({ current_step }: Props) {
  if (!current_step) return null

  return (
    <div className="flex gap-0.5 items-center">
      {steps.map((s) => {
        const status = getStepStatus(s.key, current_step)
        if (status === 'pending' && s.key === 'fixing') return null // hide F if never used
        return (
          <span
            key={s.key}
            title={`${s.title} (${status})`}
            className={`w-5 h-5 flex items-center justify-center rounded text-sm font-bold ${stepStyle[status] ?? stepStyle.pending}`}
          >
            {s.label}
          </span>
        )
      })}
    </div>
  )
}
