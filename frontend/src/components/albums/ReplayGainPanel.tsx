import { useState } from 'react'
import { Volume2, Play } from 'lucide-react'
import type { AlbumDetail } from '@/types'
import { calculateReplayGain } from '@/services/api'
import { useNotificationStore } from '@/store/useNotificationStore'
import { LoadingSpinner } from '@/components/common'

interface Props {
  album: AlbumDetail
}

export function ReplayGainPanel({ album }: Props) {
  const [calculating, setCalculating] = useState(false)
  const addToast = useNotificationStore((s) => s.addToast)

  const handleCalculate = async () => {
    setCalculating(true)
    try {
      await calculateReplayGain(album.id)
      addToast('info', 'ReplayGain calculation started (background task)')
    } catch {
      addToast('error', 'Failed to start ReplayGain calculation')
    } finally {
      setCalculating(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Volume2 className="h-4 w-4 text-text-muted" />
          <span className="text-sm text-text">ReplayGain</span>
          {album.replaygain_album_gain && (
            <span className="text-xs font-mono text-accent-green">
              Album: {album.replaygain_album_gain}
            </span>
          )}
        </div>
        <button
          onClick={handleCalculate}
          disabled={calculating}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-accent-blue hover:bg-accent-blue/10 rounded-lg transition-colors disabled:opacity-50"
        >
          {calculating ? <LoadingSpinner size="sm" /> : <Play className="h-3.5 w-3.5" />}
          Calculate
        </button>
      </div>

      {album.replaygain_album_gain && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="px-3 py-2 bg-surface-200 rounded-lg">
            <span className="text-text-subtle">Album Gain</span>
            <p className="font-mono text-text">{album.replaygain_album_gain}</p>
          </div>
          <div className="px-3 py-2 bg-surface-200 rounded-lg">
            <span className="text-text-subtle">Album Peak</span>
            <p className="font-mono text-text">{album.replaygain_album_peak}</p>
          </div>
        </div>
      )}
    </div>
  )
}
