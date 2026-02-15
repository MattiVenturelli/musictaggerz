import { useEffect, useRef, useState } from 'react'
import { Loader2, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react'
import { useAlbumStore, type ProgressInfo } from '@/store/useAlbumStore'
import { cn } from '@/utils'

interface Props {
  albumId: number
}

interface LogEntry {
  progress: number
  message: string
  time: number
}

export function ProgressPanel({ albumId }: Props) {
  const activeProgress = useAlbumStore((s) => s.activeProgress)
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const [completed, setCompleted] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const prevAlbumId = useRef<number | null>(null)

  // Accumulate log entries when progress updates arrive
  useEffect(() => {
    if (!activeProgress || activeProgress.albumId !== albumId) return

    // Reset log if it's a new album
    if (prevAlbumId.current !== albumId) {
      setLogEntries([])
      setCompleted(false)
      prevAlbumId.current = albumId
    }

    setLogEntries((prev) => {
      const last = prev[prev.length - 1]
      // Skip duplicates
      if (last && last.message === activeProgress.message) return prev
      return [...prev, {
        progress: activeProgress.progress,
        message: activeProgress.message,
        time: Date.now(),
      }]
    })
  }, [activeProgress, albumId])

  // When progress is cleared (terminal status), show "Complete" for a few seconds
  useEffect(() => {
    if (!activeProgress && logEntries.length > 0 && !completed) {
      setCompleted(true)
      dismissTimer.current = setTimeout(() => {
        setLogEntries([])
        setCompleted(false)
        prevAlbumId.current = null
      }, 5000)
    }

    return () => {
      if (dismissTimer.current) clearTimeout(dismissTimer.current)
    }
  }, [activeProgress, logEntries.length, completed])

  const isActive = activeProgress && activeProgress.albumId === albumId
  const showPanel = isActive || completed

  if (!showPanel) return null

  const pct = completed ? 100 : Math.round((activeProgress?.progress ?? 0) * 100)
  const currentMessage = completed
    ? 'Complete!'
    : activeProgress?.message || 'Processing...'

  return (
    <div className={cn(
      'rounded-xl p-4 space-y-3 transition-all duration-300',
      completed
        ? 'bg-accent-green/5 border border-accent-green/20'
        : 'bg-accent-blue/5 border border-accent-blue/20'
    )}>
      <div className="flex items-center gap-3">
        {completed ? (
          <CheckCircle2 className="h-5 w-5 text-accent-green shrink-0" />
        ) : (
          <Loader2 className="h-5 w-5 text-accent-blue animate-spin shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text">
            {completed ? 'Done' : 'Processing...'}
          </p>
          <p className="text-sm text-text-muted truncate">{currentMessage}</p>
        </div>
        <span className={cn(
          'text-sm font-medium tabular-nums',
          completed ? 'text-accent-green' : 'text-accent-blue'
        )}>
          {pct}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-surface-400 overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-300 ease-out',
            completed ? 'bg-accent-green' : 'bg-accent-blue'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Log entries */}
      {logEntries.length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-text-subtle hover:text-text-muted transition-colors"
          >
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {expanded ? 'Hide' : 'Show'} log ({logEntries.length} steps)
          </button>
          {expanded && (
            <div className="mt-2 space-y-0.5 max-h-40 overflow-y-auto">
              {logEntries.map((entry, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-text-subtle">
                  <span className="tabular-nums text-text-muted w-8 text-right shrink-0">
                    {Math.round(entry.progress * 100)}%
                  </span>
                  <span className="truncate">{entry.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
