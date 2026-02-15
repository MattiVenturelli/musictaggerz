import { useState } from 'react'
import { Image, Check, Loader2 } from 'lucide-react'
import type { AlbumDetail, ArtworkOption } from '@/types'
import { fetchArtworkOptions, applyArtwork } from '@/services/api'
import { useAlbumStore } from '@/store/useAlbumStore'
import { useNotificationStore } from '@/store/useNotificationStore'
import { cn } from '@/utils'

interface Props {
  album: AlbumDetail
}

const SOURCE_BADGES: Record<string, { label: string; className: string }> = {
  caa: { label: 'CAA', className: 'bg-accent-blue/20 text-accent-blue' },
  itunes: { label: 'iTunes', className: 'bg-[#fb923c]/20 text-[#fb923c]' },
  fanarttv: { label: 'fanart.tv', className: 'bg-accent-green/20 text-accent-green' },
  filesystem: { label: 'Local', className: 'bg-accent-yellow/20 text-accent-yellow' },
}

export function ArtworkChooser({ album }: Props) {
  const { fetchAlbum } = useAlbumStore()
  const addToast = useNotificationStore((s) => s.addToast)

  const [options, setOptions] = useState<ArtworkOption[]>([])
  const [selected, setSelected] = useState<ArtworkOption | null>(null)
  const [discovering, setDiscovering] = useState(false)
  const [applying, setApplying] = useState(false)
  const [discovered, setDiscovered] = useState(false)

  const handleDiscover = async () => {
    setDiscovering(true)
    setSelected(null)
    try {
      const resp = await fetchArtworkOptions(album.id)
      setOptions(resp.options)
      setDiscovered(true)
      if (resp.options.length === 0) {
        addToast('info', 'No artwork found from any source')
      }
    } catch {
      addToast('error', 'Failed to discover artwork')
    } finally {
      setDiscovering(false)
    }
  }

  const handleApply = async () => {
    if (!selected) return
    setApplying(true)
    try {
      await applyArtwork(album.id, {
        source: selected.source,
        full_url: selected.full_url,
        file: selected.source === 'filesystem' ? selected.label : undefined,
      })
      addToast('success', 'Artwork applied successfully')
      fetchAlbum(album.id)
    } catch {
      addToast('error', 'Failed to apply artwork')
    } finally {
      setApplying(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={handleDiscover}
          disabled={discovering}
          className="flex items-center gap-2 px-4 py-2 bg-surface-400 text-text rounded-lg text-sm font-medium hover:bg-surface-500 disabled:opacity-50 transition-colors"
        >
          {discovering ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Image className="h-4 w-4" />
          )}
          {discovering ? 'Searching...' : 'Find Artwork'}
        </button>

        {selected && (
          <button
            onClick={handleApply}
            disabled={applying}
            className="flex items-center gap-2 px-4 py-2 bg-accent-green text-surface-300 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {applying ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            Apply Selected Artwork
          </button>
        )}
      </div>

      {discovered && options.length > 0 && (
        <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 gap-3">
          {options.map((opt, i) => (
            <ArtworkThumbnail
              key={`${opt.source}-${i}`}
              option={opt}
              selected={selected === opt}
              onSelect={() => setSelected(opt)}
            />
          ))}
        </div>
      )}

      {discovered && options.length === 0 && !discovering && (
        <p className="text-sm text-text-subtle">No artwork options found.</p>
      )}
    </div>
  )
}

function ArtworkThumbnail({
  option,
  selected,
  onSelect,
}: {
  option: ArtworkOption
  selected: boolean
  onSelect: () => void
}) {
  const [imgError, setImgError] = useState(false)
  const badge = SOURCE_BADGES[option.source] || { label: option.source, className: 'bg-surface-400 text-text-muted' }

  return (
    <button
      onClick={onSelect}
      className={cn(
        'relative rounded-lg border-2 overflow-hidden transition-all aspect-square',
        selected
          ? 'border-accent-blue ring-2 ring-accent-blue/30'
          : 'border-surface-400 hover:border-surface-500'
      )}
    >
      {!imgError ? (
        <img
          src={option.thumbnail_url}
          alt={option.label}
          className="w-full h-full object-cover"
          onError={() => setImgError(true)}
          loading="lazy"
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center bg-surface-200">
          <Image className="h-8 w-8 text-surface-500" />
        </div>
      )}

      {/* Selection checkmark */}
      {selected && (
        <div className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-accent-blue flex items-center justify-center">
          <Check className="h-3.5 w-3.5 text-white" />
        </div>
      )}

      {/* Source badge */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-1.5 pt-4">
        <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded', badge.className)}>
          {badge.label}
        </span>
      </div>

      {/* Label tooltip */}
      {option.label && (
        <div className="absolute top-0 left-0 right-0 bg-gradient-to-b from-black/50 to-transparent p-1.5 pb-4 opacity-0 hover:opacity-100 transition-opacity">
          <p className="text-[10px] text-white truncate">{option.label}</p>
        </div>
      )}
    </button>
  )
}
