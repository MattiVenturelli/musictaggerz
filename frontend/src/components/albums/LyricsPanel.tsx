import { useState } from 'react'
import { Music2, Download } from 'lucide-react'
import type { AlbumDetail } from '@/types'
import { fetchAlbumLyrics } from '@/services/api'
import { useAlbumStore } from '@/store/useAlbumStore'
import { useNotificationStore } from '@/store/useNotificationStore'
import { LoadingSpinner } from '@/components/common'

interface Props {
  album: AlbumDetail
}

export function LyricsPanel({ album }: Props) {
  const [fetching, setFetching] = useState(false)
  const [result, setResult] = useState<{ found: number; not_found: number; errors: number } | null>(null)
  const fetchAlbum = useAlbumStore((s) => s.fetchAlbum)
  const addToast = useNotificationStore((s) => s.addToast)

  const lyricsCount = album.tracks.filter((t) => t.has_lyrics).length
  const syncedCount = album.tracks.filter((t) => t.lyrics_synced).length

  const handleFetch = async () => {
    setFetching(true)
    setResult(null)
    try {
      const res = await fetchAlbumLyrics(album.id)
      setResult(res)
      addToast('success', `Lyrics: ${res.found} found, ${res.not_found} not found`)
      fetchAlbum(album.id)
    } catch {
      addToast('error', 'Failed to fetch lyrics')
    } finally {
      setFetching(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Music2 className="h-4 w-4 text-text-muted" />
          <span className="text-sm text-text">Lyrics</span>
          {lyricsCount > 0 && (
            <span className="text-xs text-text-subtle">
              {lyricsCount}/{album.tracks.length} tracks
              {syncedCount > 0 && ` (${syncedCount} synced)`}
            </span>
          )}
        </div>
        <button
          onClick={handleFetch}
          disabled={fetching}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-accent-blue hover:bg-accent-blue/10 rounded-lg transition-colors disabled:opacity-50"
        >
          {fetching ? <LoadingSpinner size="sm" /> : <Download className="h-3.5 w-3.5" />}
          Fetch Lyrics
        </button>
      </div>

      {result && (
        <div className="text-xs text-text-subtle px-2">
          Found: {result.found} · Not found: {result.not_found}
          {result.errors > 0 && ` · Errors: ${result.errors}`}
        </div>
      )}
    </div>
  )
}
