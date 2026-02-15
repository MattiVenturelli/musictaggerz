import { formatConfidence, getConfidenceBgColor, getConfidenceColor, cn } from '@/utils'

interface Props {
  confidence: number | null
  showLabel?: boolean
  className?: string
}

export function ConfidenceIndicator({ confidence, showLabel = true, className }: Props) {
  if (confidence == null) return null

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="h-1.5 w-16 rounded-full bg-surface-400 overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', getConfidenceBgColor(confidence))}
          style={{ width: `${Math.min(confidence, 100)}%` }}
        />
      </div>
      {showLabel && (
        <span className={cn('text-xs font-medium', getConfidenceColor(confidence))}>
          {formatConfidence(confidence)}
        </span>
      )}
    </div>
  )
}
