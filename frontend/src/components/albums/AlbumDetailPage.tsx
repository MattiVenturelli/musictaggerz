import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Disc3, ExternalLink } from 'lucide-react'
import { useAlbumStore } from '@/store/useAlbumStore'
import { LoadingSpinner, StatusBadge, ConfidenceIndicator } from '@/components/common'
import { getAlbumCoverUrl } from '@/services/api'
import { TrackList } from './TrackList'
import { MatchReviewPanel } from './MatchReviewPanel'

export function AlbumDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentAlbum: album, detailLoading, fetchAlbum } = useAlbumStore()
  const [imgError, setImgError] = useState(false)

  useEffect(() => {
    if (id) {
      fetchAlbum(parseInt(id))
      setImgError(false)
    }
  }, [id, fetchAlbum])

  if (detailLoading || !album) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="max-w-5xl space-y-6">
      {/* Back button */}
      <button
        onClick={() => navigate('/albums')}
        className="flex items-center gap-2 text-sm text-text-muted hover:text-text transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Albums
      </button>

      {/* Header */}
      <div className="flex gap-6">
        {/* Cover */}
        <div className="w-48 h-48 rounded-xl bg-surface-200 overflow-hidden shrink-0 border border-surface-400">
          {!imgError ? (
            <img
              src={getAlbumCoverUrl(album.id)}
              alt={`${album.artist} - ${album.album}`}
              className="w-full h-full object-cover"
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Disc3 className="h-20 w-20 text-surface-500" />
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <StatusBadge status={album.status} />
            {album.match_confidence != null && (
              <ConfidenceIndicator confidence={album.match_confidence} />
            )}
          </div>
          <h1 className="text-2xl font-bold text-text truncate">
            {album.album || 'Unknown Album'}
          </h1>
          <p className="text-lg text-text-muted mt-1">
            {album.artist || 'Unknown Artist'}
            {album.year ? ` (${album.year})` : ''}
          </p>
          <div className="mt-3 text-xs text-text-subtle space-y-1">
            <p>{album.track_count || 0} tracks</p>
            <p className="truncate" title={album.path}>{album.path}</p>
            {album.musicbrainz_release_id && (
              <a
                href={`https://musicbrainz.org/release/${album.musicbrainz_release_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-accent-blue hover:underline"
              >
                MusicBrainz <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Actions / Match review */}
      <div className="bg-surface-100 rounded-xl border border-surface-400 p-5">
        <h2 className="text-sm font-medium text-text-muted mb-4">Actions & Matching</h2>
        <MatchReviewPanel album={album} />
      </div>

      {/* Track list */}
      <div className="bg-surface-100 rounded-xl border border-surface-400 p-5">
        <h2 className="text-sm font-medium text-text-muted mb-4">Tracks</h2>
        <TrackList tracks={album.tracks} />
      </div>
    </div>
  )
}
