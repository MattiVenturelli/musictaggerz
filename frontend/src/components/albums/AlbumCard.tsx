import { useNavigate } from 'react-router-dom'
import { Disc3 } from 'lucide-react'
import type { AlbumSummary } from '@/types'
import { StatusBadge, ConfidenceIndicator } from '@/components/common'
import { getAlbumCoverUrl } from '@/services/api'
import { cn } from '@/utils'
import { useState } from 'react'

interface Props {
  album: AlbumSummary
  selected: boolean
  onToggleSelect: (id: number) => void
}

export function AlbumCard({ album, selected, onToggleSelect }: Props) {
  const navigate = useNavigate()
  const [imgError, setImgError] = useState(false)

  return (
    <div
      className={cn(
        'bg-surface-100 rounded-xl border overflow-hidden cursor-pointer transition-all hover:border-accent-blue/50 hover:shadow-lg group',
        selected ? 'border-accent-blue ring-1 ring-accent-blue/30' : 'border-surface-400'
      )}
    >
      <div className="relative aspect-square bg-surface-200" onClick={() => navigate(`/albums/${album.id}`)}>
        {!imgError ? (
          <img
            src={getAlbumCoverUrl(album.id)}
            alt={`${album.artist} - ${album.album}`}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Disc3 className="h-16 w-16 text-surface-500" />
          </div>
        )}
        <div className="absolute top-2 left-2">
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => {
              e.stopPropagation()
              onToggleSelect(album.id)
            }}
            onClick={(e) => e.stopPropagation()}
            className="h-4 w-4 rounded border-surface-500 bg-surface-200 text-accent-blue focus:ring-accent-blue cursor-pointer"
          />
        </div>
        <div className="absolute top-2 right-2">
          <StatusBadge status={album.status} />
        </div>
      </div>

      <div className="p-3" onClick={() => navigate(`/albums/${album.id}`)}>
        <p className="text-sm font-medium text-text truncate">
          {album.album || 'Unknown Album'}
        </p>
        <p className="text-xs text-text-muted truncate mt-0.5">
          {album.artist || 'Unknown Artist'}
          {album.year ? ` (${album.year})` : ''}
        </p>
        {album.match_confidence != null && (
          <div className="mt-2">
            <ConfidenceIndicator confidence={album.match_confidence} />
          </div>
        )}
      </div>
    </div>
  )
}
