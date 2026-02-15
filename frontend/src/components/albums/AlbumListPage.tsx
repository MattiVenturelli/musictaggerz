import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Disc3 } from 'lucide-react'
import { useAlbumStore } from '@/store/useAlbumStore'
import { LoadingSpinner, EmptyState, Pagination } from '@/components/common'
import { AlbumCard } from './AlbumCard'
import { AlbumFilters } from './AlbumFilters'
import type { AlbumStatus } from '@/types'

export function AlbumListPage() {
  const { albums, total, filters, loading, selectedIds, toggleSelect, fetchAlbums, setFilters } = useAlbumStore()
  const [searchParams] = useSearchParams()

  // Apply status filter from URL query param (e.g. /albums?status=tagged)
  useEffect(() => {
    const urlStatus = searchParams.get('status') as AlbumStatus | null
    if (urlStatus && urlStatus !== filters.status) {
      setFilters({ status: urlStatus })
    } else if (!urlStatus && !filters.status) {
      fetchAlbums()
    }
  }, [searchParams])

  return (
    <div className="max-w-7xl space-y-6">
      <h1 className="text-2xl font-bold text-text">Albums</h1>

      <AlbumFilters />

      {loading && albums.length === 0 ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : albums.length === 0 ? (
        <EmptyState
          icon={Disc3}
          title="No albums found"
          description="Try adjusting your filters or scan your music directory."
        />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {albums.map((album) => (
              <AlbumCard
                key={album.id}
                album={album}
                selected={selectedIds.has(album.id)}
                onToggleSelect={toggleSelect}
              />
            ))}
          </div>

          <div className="flex justify-center">
            <Pagination
              total={total}
              limit={filters.limit || 50}
              offset={filters.offset || 0}
              onPageChange={(offset) => setFilters({ offset })}
            />
          </div>
        </>
      )}
    </div>
  )
}
